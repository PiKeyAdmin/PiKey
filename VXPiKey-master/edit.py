from metagame import *
from ddr import *
from cmd import *
from pimidi import *
from piece import *
import pygame
import midi as MIDI # van python-midi vishnubob github, voor het makkelijk "reading/writing" van midi bestanden.
import config
from collections import deque # voor het snel poppen van lists.
import itertools
import mingus.core.chords as CHORDS
import mingus.core.notes as NOTES

class EditClass( DDRClass ): # erft van de DDR class.
#### EDIT CLASS
    def __init__( self, piecedir, midi, piecesettings = { 
            "TempoPercent" : 100, "Difficulty" : 0,
            "BookmarkTicks" : [],
            "AllowedDifficulties" : [ 0 ],
            "Sandbox" : config.SANDBOXplay,
            "PlayerStarts" : config.PLAYERstarts,
            "PlayerTrack" : 0,
            "Metronome" : config.METRONOMEdefault } ):
        DDRClass.__init__( self, piecedir, midi, piecesettings )
        self.noteson = {} # notes die je inklikt en na een bepaalde tijd uitgaan.
        self.sandbox = 1 # in edit mode moet je 100% Sandbox zijn gang laten gaan, alles gaat mis als dit niet zo is.
        self.currentvelocity = 100 # standaard note velocity.
        self.currenttrack = 0
        self.noteclipboard = [] # voor copy pasting
    
        # set the default state of the editor
        self.allowedchanges = [ 'state' ]
        self.state = -1
        #self.EXITstate = 0 # 
        self.NAVIGATIONstate = 1 # standaard staat als je escape inklikt.  voor copy/pasting, etc.  
        self.SELECTstate = 2 # visual block/line type stuff
        self.COMMANDstate = 3 # after pressing escape, then colon (:).  vim-like command mode
        self.INSERTstate = 4 # nadat je i,I, a,A, inklikt kan je noten maken op je keyboard
        self.CHORDstate = 5 

        self.commandlist = deque([], config.COMMANDhistory) 
        self.commandlistindex = -1
        self.commandfont = config.FONT
        self.commandfontcolor = (255,255,255)
        self.commandfontsize = int(24*config.FONTSIZEmultiplier)
        self.commandbackcolor = (0, 0, 0)
        self.helperfontcolor = (255,255,255)
        self.helperfontsize = int(18*config.FONTSIZEmultiplier)
        self.helperbackcolor = (0, 0, 0)
        self.statenames = { self.NAVIGATIONstate : "Navigation",
                            self.SELECTstate : "Select",
                            self.COMMANDstate : "Command",
                            self.INSERTstate : "Insert",
                            self.CHORDstate : "Chord" }
        self.helper = { 
            self.NAVIGATIONstate : [ 0, #start line
                 [ " ctrl+j|k   scroll deze helper lijst down|up",
                   "   ctrl+/   search deze helper lijst",
                   " ctrl+n|N   herhaal het zoeken forward|backward",
                   "",
                   "  h|j|k|l   beweeg left|down|up|right",
                   "  H|J|K|L   beweeg left|down|up|right faster",
                   "      g|G   ga naar beginning|end van de piece",
                   "    SPACE   start/stop piece playing",
                   "",
                   "      e|E   verleng noten bij half|full ",
                   "        s   verklein noten",

                   "",
                   "  PgUp|Dn   beweeg up|down met een scherm",
                   " HOME|END   beweeg helemaal naar left|right links of rechts",
                    ]
               ],
            self.SELECTstate : [ 0, #start line
                 [ "ctrl+j|k    scroll deze helper lijst down|up",
                   " h|j|k|l    beweeg left|down|up|right" ]
               ],
            self.COMMANDstate : [ 0, #start line
                 [ "ctrl+j|k    scroll deze helper lijst down|up",
                   "  ESCAPE    go terug naar navigation mode",
                   " up|down    navigeer command history",
                   " PgUp|Dn    verwijder command",
                   " ",
                   "Typ en klik enter:",
                   "  q|quit    sluit PiKey",
                   "s|save|w    save piece",
                   "  return    terug naar main menu ",
                   "  reload    herhaal de piece van de safe file",
                   "   clear    leeg de piece",
                   "",
                   "     i X    verander instrument naar X,"
                   "            X kan een nummer van (0 to 127) zijn, of een naam",
                   "     v X    set quick-input velocity to X (0 to 127)",
                   "     o X    open difficulty X",
                   ]
               ],
            }

        # in deze helper zie je al je commands die je kan gebruiken als je "escape" inklikt -  escape maakt je cmd aka command prompt open.
        self.helperlines = [] 
        self.lasthelpsearched = ""
        self.helperlinemax = max(1, config.HELPERLINEmax)

        self.setstate( state=self.NAVIGATIONstate )

        # de onderste variabele zijn voor de bovengenoemde onderdelen.:
        self.insertmode = 0    
        self.waitforkeytoplay = 0

        # om de helper te krijgen en command informatie te krijgen
        self.commander = CommandClass( self.docommand, "cmd" )
        self.chordcommander = CommandClass( self.addquickchordinselection, "quick chord" )
        
        self.preemptor = None
        #self.preemptingfor = { 
            #"search help" : CommandClass( self.searchhelp, "search help" ),
            #"scale factor" : CommandClass( self.scalecursorselection, "scale factor" )
        #}

        self.anchor = 0 #gaat naar [ midinote, anchorposition ]

	# Om tracks toe te voegen en vertelt je of je de gegeven positie wel kan gebruiken of niet.
    def addtrack( self ):
        self.piece.addtrack()
        self.noisytracks.add( len(self.piece.notes)-1 )

    def setstate( self, **kwargs ):
        for key, value in kwargs.iteritems():
            if key in self.allowedchanges:
                setattr( self, key, value )
                if key == "state":
                    self.setalert("Now in "+self.statenames[value])
                    self.sethelperlines( value )
            else:
                Warn("in EditClass:setstate - key "+ key +" is protected!!") 

    def update( self, dt, midi ):
        DDRClass.update( self, dt, midi )

    def process( self, event, midi ):
        '''hieronder zijn de methodes om dingen te veranderen, dit is niet voor
		   midi input maar juist voor midi output, zo kan je dan zien wanner je wat doet
		   bijvoorbeeld als je geen midi apparaat gebruikt om te kijken of er geluid is.'''

        if self.preemptor:
            if len(self.preemptor.process( event, midi )):
                self.preemptor = None
            return {}

        elif self.metanav( event, midi ):
            return {}

        elif self.state == self.NAVIGATIONstate:
            return self.navprocess( event, midi )
        
        elif self.state == self.INSERTstate:
            return self.insprocess( event, midi )
        
        elif self.state == self.COMMANDstate:
            return self.commander.process( event, midi )

        elif self.state == self.CHORDstate:
            return self.chordcommander.process( event, midi )

        else:
            Error(" UNKNOWN state in EditClass.process( self, event, midi ) ")
        return {}

    def navprocess( self, event, midi ):
        # NAVIGATIE: Als je ESC inklint dan kom je bij dit menu.
        if event.type == pygame.KEYDOWN:
            if ( event.key == 27 ):
                if self.anchor:
                    self.anchor = 0
                else:
                    self.setstate( state=self.COMMANDstate ) 
            elif event.key == pygame.K_i or event.key == pygame.K_a:
                # insert mode.  i = hier kan je dingen toevoegen op de huidige positie(key), a = set insert
                if event.key == pygame.K_a:
                    self.waitforkeytoplay = 1
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    self.insertmode = 1
                else:
                    self.insertmode = 0 
                self.setstate( state=self.INSERTstate )

            elif event.key == pygame.K_q:
                # quick insert
                if self.anchor:
                    self.setstate( state=self.CHORDstate ) 
                    self.setalert("Choose shorthand chord") 
                else:
                    self.addnoteatcursor( midi )
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        self.setcurrentticksandload( self.currentabsoluteticks + self.currentnoteticks )
                # NEED NEW FUNCTIONALITY FOR SELECTIONS.
            elif event.key == pygame.K_d:
                self.deletecursorselection( pygame.key.get_mods() & pygame.KMOD_SHIFT )
            
            
            elif event.key == pygame.K_s:
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    self.setalert("Scale geselecteerde noten")
                    self.preemptor = self.preemptingfor[ "scale factor" ]
                else:
                    self.shortencursorselection()
            
            elif event.key == pygame.K_e:
                self.extendcursorselection( pygame.key.get_mods() & pygame.KMOD_SHIFT )

            elif event.key == pygame.K_LEFTBRACKET:
                # verlaag volume niveau
                self.changevelocityatcursorselection( midi, -1, pygame.key.get_mods() & pygame.KMOD_SHIFT )
            elif event.key == pygame.K_RIGHTBRACKET:
                # verhoog volume niveau
                self.changevelocityatcursorselection( midi,  1, pygame.key.get_mods() & pygame.KMOD_SHIFT )
            
            elif event.key == pygame.K_RETURN:
                # speelt geselcteerde noten af
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    # als je "SHIFT" inklikt speelt het de hele stuk/lijn
                    currentticks = self.roundtonoteticks( self.currentabsoluteticks )
                    if self.anchor:
                        originalanchor0 = self.anchor[0]
                        self.anchor[0] = -1
                    else:
                        originalanchor0 = None
                        self.anchor = [ -1, currentticks ]

                    # checkt of er geselecteerde noten zijn
                    self.selectcursorselection()
                    if self.selectednotes:
                        for note in self.selectednotes:
                            # slaat key aan:
                            self.keymusic.hitkey( midi, note[0], 
                                note[1], self.tickstosecs(note[2]),
                                self.piece.channels[self.currenttrack], True 
                            )
                    else:
                        if self.anchor[1] != currentticks:
                            self.setalert("Geen noten om af te spelen.")
                        else:
                            self.setalert("Geen noten om af te spelen")

                    if originalanchor0 == None:
                        self.anchor = 0
                    else:
                        self.anchor = [ originalanchor0, self.anchor[1] ]
                else:
                    # geen noten zijn geselecteerd
                    self.keymusic.hitkey( midi, self.keymusic.cursorkeyindex + config.LOWESTnote,
                        100,    # velocity
                        1,      # looptijd
                        self.piece.channels[self.currenttrack], 
                        True  # speelt geluid af
                    )

            elif self.commonnav( event, midi ):        
                return {}
            elif self.commongrid( event, midi ):
                return {}

        return {}

    def insprocess( self, event, midi ):
        if event.type == pygame.KEYDOWN:
            if event.key == 27:
                self.setstate( state=self.NAVIGATIONstate  )
            elif (event.key == pygame.K_SLASH
                   or event.key == pygame.K_SEMICOLON or event.key == pygame.K_COLON ):
                self.setstate( state=self.COMMANDstate  ) 
            elif (event.key == pygame.K_i):
                self.waitforkeytoplay = 1 - self.waitforkeytoplay
                if self.waitforkeytoplay:
                    if config.SMALLalerts:
                        self.setalert( "Piano rolt op input" )
                    else:
                        self.setalert( "Als je op een knop klikt dan gaat het beeld bewegen" )
                else:
                    self.setalert( "Piano statisch op input" )
            elif (event.key == pygame.K_i):
                self.insertmode = 1 - self.insertmode
                if self.insertmode:
                    self.setalert( "Aggressive insert" )
                else:
                    self.setalert( "Friendly insert" )
            elif self.commonnav( event, midi ):
                return {}
            elif self.commongrid( event, midi ):
                return {}
        return {}
    
    def docommand( self, command, midi ):
        if command:
            if command == "quit" or command == "q":
                return { "gamestate" : 0, "printme" : "Stop edit mode" } 
            elif command == "return":
                midi.clearall()
                return { "gamestate" : config.GAMESTATEmainmenu, 
                         "printme" : "terug van edit mode" } 
            elif command == "reload":
                midi.clearall()
                self.__init__( self.piece.piecedir, midi )
                return { "printme" : "herladen van de file" }
            elif command == "save" or command == "s" or command == "w":
                self.piece.settings["BookmarkTicks"] = self.bookmarkticks
                self.piece.writeinfo()
                self.piece.writemidi()
                return self.wrapupcommand( self.piece.piecedir+"/"+str(self.piece.settings["Difficulty"])+" saved!" )
            elif command == "clear" or command == "reset":
                midi.clearall()
                self.piece.clear()
                self.play = False
                self.setcurrentticksandload(0)
                return self.wrapupcommand( "alle noten zijn verwijderd." )
            else:
                split = command.split()

 
        self.setstate( state=self.NAVIGATIONstate  )
        return { "printme" : "terug naar navigation" }

    def wrapupcommand( self, alert ):
        self.setstate( state=self.NAVIGATIONstate  )
        self.setalert( alert )
        return { "printme" : alert }

#### EDIT CLASS
    def processmidi( self, midi ):
        newnoteson = midi.newnoteson()
        for note in newnoteson:
            midi.startnote( note[0], note[1], self.currenttrack )
            # verlicht de noot in de background
            self.keymusic.brightenkey( note[0], note[1] ) 
            
        newnotesoff = midi.newnotesoff()
        for note in newnotesoff:
            midi.endnote( note, self.currenttrack ) # stop de note

        if self.state == self.INSERTstate:
            if len(newnoteson): 
                if not self.play:  # ials we niet aan het spelen zijn
                    if self.waitforkeytoplay: # kijk of je aan het wachten bent voor een key
                        self.play = True

            for note in newnoteson:
                self.addnoteonpresently( midi, note[0], note[1], False )


            if self.play:
                # als je aan het spelen bent, laat de noten ergens vallen
                for note in newnotesoff:
                    self.addnoteoffpresently( midi, note )
            else:
                # als je niet aan het spelen bent, laat de noten zijn bij je currentoffsetticks
                for note in newnotesoff:
                    self.addnoteoffpresently( midi, note, self.currentnoteticks )
        
        return {}

    def sethelperlines( self, state ):
        start = self.helper[ state ][0] 
        self.helperlines = ([ (self.statenames[ state ]).upper() ] 
                            + self.helper[ state ][1][ start : start+self.helperlinemax ])
        
        if len(self.helperlines):
            fontandsize = pygame.font.SysFont(config.FONT, self.helperfontsize)
            self.helperlabel = []
            self.helperlabelbox = []
            self.maxhelperwidth = 0
            for i in range(len(self.helperlines)):
                self.helperlabel.append( fontandsize.render( self.helperlines[i], 1, self.helperfontcolor ) )
                self.helperlabelbox.append( self.helperlabel[-1].get_rect() )
                if self.helperlabelbox[i].width > self.maxhelperwidth:
                    self.maxhelperwidth = self.helperlabelbox[i].width
        
    def metanav( self, event, midi ):
        # metanavigatie is voor alles wat ctrl gebaseerd is.
        if event.type == pygame.KEYDOWN and pygame.key.get_mods() & pygame.KMOD_CTRL:
            if event.key == pygame.K_j or event.key == pygame.K_DOWN: # klik op de down key
                # beweeg naar beneden in de helper lijst
                if self.helper[ self.state ][0] < len(self.helper[ self.state ][1]) - self.helperlinemax:
                    self.helper[ self.state ][0] += 1
                    self.sethelperlines( self.state )
                else:
                    self.setalert("Aan het einde van de help lijst.")
                return 1
            elif event.key == pygame.K_k or event.key == pygame.K_UP: # press up
                # beweeg naar de beneden in de helperlijst
                if self.helper[ self.state ][0] > 0:
                    self.helper[ self.state ][0] -= 1
                    self.sethelperlines( self.state )
                else:
                    self.setalert("In het begin van de help lijst.")
                return 1
            elif event.key == pygame.K_g:
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    self.helper[ self.state ][0] = len(self.helper[ self.state ][1])-self.helperlinemax
                    self.setalert("Aan het einde van de help lijst.")
                else:
                    self.setalert("In het begin van de help lijst.")
                    self.helper[ self.state ][0] = 0
                self.sethelperlines( self.state )
                return 1
            elif event.key == pygame.K_PAGEUP:
                if self.helper[ self.state ][0] > self.helperlinemax:
                    self.helper[ self.state ][0] -= self.helperlinemax
                else:
                    self.helper[ self.state ][0] = 0
                    self.setalert("In het begin van de help lijst.")
                self.sethelperlines( self.state )
                return 1
            elif event.key == pygame.K_PAGEDOWN:
                if self.helper[ self.state ][0] < len(self.helper[ self.state ][1]) - 2*self.helperlinemax:
                    self.helper[ self.state ][0] += self.helperlinemax
                else:
                    self.setalert("Aan het einde van de help lijst.")
                    self.helper[ self.state ][0] = len(self.helper[ self.state ][1])-self.helperlinemax

                self.sethelperlines( self.state )
                return 1
                
        return 0

#### EDIT CLASS 
    
    def addremovetext( self, text ):
        return self.piece.addremovetextevent( text, self.roundtonoteticks( self.currentabsoluteticks ),
            self.currenttrack )
    
    def addmidinote( self, note ):
        if note.velocity:
            newnote = MIDI.NoteOnEvent( pitch = note.pitch,
                    velocity = note.data[1] )
        else:
            newnote = MIDI.NoteOffEvent( pitch = note.pitch )
        newnote.absoluteticks = note.absoluteticks 
        self.piece.addmidinote( newnote, self.currenttrack )

    def addnote( self, midinote, velocity, absticks, duration ):
        # abs ticks is de start van een noot, duratie is hoe lang het duurt

        # delete de noten die dichtbij zijn
        selected, midiselected = self.piece.selectnotes( 
            [absticks, absticks+duration], 
            [midinote], 
            self.currenttrack 
        )
        self.piece.deletenotes( selected, self.currenttrack )

        # voeg de noot toe
        self.piece.addnote( midinote, velocity, absticks, duration, self.currenttrack )

    def addsnote( self, midi, midinote, velocity, absticks, duration, playsound=True ):
        ''' add sounded note '''
        self.addnote( midinote, velocity, absticks, duration )

        # and hit a key
        self.keymusic.hitkey( midi, midinote, velocity, self.tickstosecs( duration ),
                              self.piece.channels[self.currenttrack], playsound )

        if not self.play:
            # als je niet aan het spelen bent, luid de noten die gespeeld zijn
            self.setcurrentticksandload( self.currentabsoluteticks )
        else:
            # je wil niet dat je geluid 2x hoort, dus bv. door de computer en door de gebruiker
            #daarom note on als je aan het spelen bent, gebruiker wijs
            reltickpixels = (absticks-self.currentabsoluteticks)* self.pixelspertick
            self.keymusic.addnote( midinote, velocity, reltickpixels )
            reltickpixels += (duration)* self.pixelspertick
            self.keymusic.addnote( midinote, 0, reltickpixels )
            

    def addnotepresently( self, midi, midinote, velocity=100, playsound=True ):
        # voeg noot toe bij abs ticks van nu
        self.addsnote( midi, midinote, velocity, 
                      self.roundtonoteticks( self.currentabsoluteticks ), 
                      self.currentnoteticks-1, playsound )
    
    def addnoteonpresently( self, midi, midinote, velocity=100, playsound=True ):
        # voeg noot toe bij abs ticks met noot duratie
        self.noteson[ midinote ] = [ velocity, self.roundtonoteticks( self.currentabsoluteticks ) ]

        self.keymusic.hitkey( midi, midinote, velocity, 1.0,
                              self.piece.channels[self.currenttrack], playsound )
    
    def addnoteoffpresently( self, midi, midinote, offset=0 ):
        try:
            note = self.noteson[ midinote ]
            # maak de noot even lang als de tick
            notelength = max(   self.currentnoteticks, 
                                ( self.roundtonoteticks( self.currentabsoluteticks ) 
                                 -note[1] + offset )   ) - config.EDITnotespace
            self.addsnote( midi, midinote, note[0], note[1], notelength, False )
            
            del self.noteson[ midinote ]

        except KeyError:
            pass

    def addnoteatcursor( self, midi ):
        self.addnotepresently( midi, self.keymusic.cursorkeyindex + config.LOWESTnote, 
                               self.currentvelocity, True ) # play sound
   
#### EDIT CLASS 

    def changevelocityofselectednotes( self, midi, change, playsound ):
        for note in self.selectedmidinotes:
            if note.name == "Note On":
                note.velocity += change
                if note.velocity > 127:
                    note.velocity = 127
                elif note.velocity <= 0:
                    note.velocity = 1

                if playsound:
                    midi.playnote( note.pitch, note.velocity, 1, 
                                   self.piece.channels[self.currenttrack] )
        
        self.setcurrentticksandload( self.currentabsoluteticks ) 
    
    def changevelocityatcursorselection( self, midi, direction, muchchange=False ):
        tickmin, tickmax, midimin, midimax = self.selectcursorselection()

        if muchchange:
            direction *= 10

        self.changevelocityofselectednotes( midi, direction, True )
        if config.SMALLalerts:
            self.setalert( "Volume changed")
        else:
            self.setalert( "Volume changed "+str(int(round(1.0*(tickmax-tickmin)/self.currentnoteticks)))+" lines." )

#### EDIT CLASS 
    
    def selectnotes( self, tickrange, midirange=None ): 
        self.selectednotes, self.selectedmidinotes = self.piece.selectnotes( 
            tickrange, midirange, self.currenttrack 
        )

    def getselectionregion( self ):
        currentticks = self.roundtonoteticks( self.currentabsoluteticks )
        if self.anchor:
            if currentticks >= self.anchor[1]:
                # we are ahead of the anchor
                tickmin = self.anchor[1]
                tickmax = currentticks + self.currentnoteticks
            else:
                # the anchor is ahead of us
                tickmin = currentticks
                tickmax = self.anchor[1] + self.currentnoteticks

            if self.anchor[0] == -1:
                midimin = config.LOWESTnote
                midimax = config.HIGHESTnote
            else:
                cursormidi = self.keymusic.cursorkeyindex + config.LOWESTnote
                if cursormidi > self.anchor[0]:
                    # je bent rechts van de anchor
                    midimax = cursormidi
                    midimin = self.anchor[0]
                else:
                    # je bent links van de anchor
                    midimax = self.anchor[0]
                    midimin = cursormidi
        else:
            tickmin = currentticks
            tickmax = tickmin + self.currentnoteticks
            midimin = self.keymusic.cursorkeyindex + config.LOWESTnote
            midimax = midimin

        return tickmin, tickmax, midimin, midimax

    def selectcursorselection( self ):
        currentticks = self.roundtonoteticks( self.currentabsoluteticks )
        if self.anchor:
            self.previousdeltaregion = []
            if currentticks >= self.anchor[1]:
                # we zijn voor de anchor
                tickmin = self.anchor[1]
                tickmax = currentticks + self.currentnoteticks
                self.previousdeltaregion.append(self.anchor[1] - currentticks)
                self.previousdeltaregion.append(self.currentnoteticks)
            else:
                # de anchor is voor ons
                tickmin = currentticks
                tickmax = self.anchor[1] + self.currentnoteticks
                self.previousdeltaregion.append(0)
                self.previousdeltaregion.append(self.anchor[1] - currentticks+ self.currentnoteticks)

            if self.anchor[0] == -1:
                midimin = config.LOWESTnote
                midimax = config.HIGHESTnote
                self.previousdeltaregion.append(-127)
                self.previousdeltaregion.append(127)
            else:
                cursormidi = self.keymusic.cursorkeyindex + config.LOWESTnote
                if cursormidi > self.anchor[0]:
                    # we zijn rechts van de anchor
                    midimax = cursormidi
                    midimin = self.anchor[0]
                    self.previousdeltaregion.append( self.anchor[0] - cursormidi )
                    self.previousdeltaregion.append(0)
                else:
                    # we zijn links van de anchor
                    midimax = self.anchor[0]
                    midimin = cursormidi
                    self.previousdeltaregion.append(0)
                    self.previousdeltaregion.append( self.anchor[0] - cursormidi )
        else:
            tickmin = currentticks
            tickmax = tickmin + self.currentnoteticks
            midimin = self.keymusic.cursorkeyindex + config.LOWESTnote
            midimax = midimin
            self.previousdeltaregion = [ 0, self.currentnoteticks, 0, 0 ]

        self.selectnotes( [tickmin,tickmax], [midimin,midimax] )
        return tickmin, tickmax, midimin, midimax

    def deletecursorselection( self, dontkeepnotes=False ):
        # quick delete
        tickmin,tickmax, midimin, midimax = self.selectcursorselection()
        if self.selectednotes:
            if dontkeepnotes:
                alerttxt = "Deleted notes from "
            else:
                self.copyselectednotes()
                alerttxt = "Cut notes into clipboard from "
            self.piece.deletenotes( self.selectednotes, self.currenttrack )
            self.setcurrentticksandload( self.currentabsoluteticks )
            if config.SMALLalerts:
                self.setalert(alerttxt[:-6])
            else:
                if midimax-midimin >= 127:
                    self.setalert( alerttxt+str(int(round(1.0*(tickmax-tickmin)/self.currentnoteticks)))+" rows")
                else:
                    self.setalert( alerttxt+str(int(round(1.0*(tickmax-tickmin)/self.currentnoteticks)))+" rows, "+
                    str(midimax-midimin+1)+" columns")
            self.anchor = 0
        else:
            self.setalert("Geen noten om te verwijderen.")
    
    def shortencursorselection( self, aggressive=False ):
        # quick delete
        tickmin,tickmax, midimin, midimax = self.selectcursorselection()
        # we have a selection going...
        self.piece.deletenotes( self.selectednotes, self.currenttrack )
        
        if self.selectednotes:
            for note in self.selectednotes:
                note[3] += config.EDITnotespace
                note[3] *= 0.5**(aggressive+1)
                if note[3] <= config.EDITshortestnote:
                    note[3] = config.EDITshortestnote
                note[3] -= config.EDITnotespace
                self.piece.addnote( note[0],note[1],note[2],note[3], self.currenttrack )
            
            if aggressive:
                alerttxt = "heel erg verkleinde noten"
            else:
                alerttxt = "noten verkleind"

            self.setcurrentticksandload( self.currentabsoluteticks )
            if config.SMALLalerts: 
                self.setalert( alerttxt[:-4] )
            else:
                if midimax-midimin >= 127:
                    self.setalert( alerttxt+str(int(round(1.0*(tickmax-tickmin)/self.currentnoteticks)))+" rows")
                else:
                    self.setalert( alerttxt+str(int(round(1.0*(tickmax-tickmin)/self.currentnoteticks)))+" rows, "+
                    str(midimax-midimin+1)+" columns")
        else:
            self.setalert("Geen noten die je kan verkleinen.")
            
    def extendcursorselection( self, aggressive=False ):
        # quick delete
        tickmin,tickmax, midimin, midimax = self.selectcursorselection()
        # we hebben een selectie gaande...
        self.piece.deletenotes( self.selectednotes, self.currenttrack )
        extension = 0.5*(aggressive+1)*self.currentnoteticks
        i = 0
        while i < len(self.selectednotes):
            notei = self.selectednotes[i]
            j = i + 1 
            while j < len(self.selectednotes):
                notej = self.selectednotes[j]
                if ( notej[0] == notei[0]   # zelfde pitch
                and notej[2] - config.EDITnotespace <= notei[2] + notei[3] + extension ):
                    # pitch is hetzelfde alleen zijn ze samengevoegd
                    # so extend notei up into notej
                    notei[3] = notej[3] + (notej[2] - notei[2])  # nog niet verlengen
                    # note j "gedood" door i:
                    del self.selectednotes[j]
                else: 
                    j += 1
            i += 1


        if self.selectednotes:
            for note in self.selectednotes:
                midinote = MIDI.NoteOnEvent( pitch=note[0], velocity=note[1] )
                midinote.absoluteticks = note[2]
                self.addmidinote( midinote )
                if self.piece.deleteonnote( note[0], [note[2], note[2]+note[3]+extension+config.EDITnotespace], 
                    self.currenttrack ):
                    midinote = MIDI.NoteOffEvent( pitch=note[0] )
                    midinote.absoluteticks = note[2]+note[3]+extension
                    self.addmidinote( midinote )

            if aggressive:
                alerttxt="aggresief erg verlengde noten "
            else:
                alerttxt="verlengde noten "

            self.setcurrentticksandload( self.currentabsoluteticks )
            if config.SMALLalerts: 
                self.setalert( alerttxt[:-4] )
            else:
                if midimax-midimin >= 127:
                    self.setalert( alerttxt+str(int(round(1.0*(tickmax-tickmin)/self.currentnoteticks)))+" rows")
                else:
                    self.setalert( alerttxt+str(int(round(1.0*(tickmax-tickmin)/self.currentnoteticks)))+" rows, "+
                    str(midimax-midimin+1)+" columns")
        else:
            self.setalert("geen noten om te verlengen.")
    
    def copyselectednotes( self ):
        self.noteclipboard = [] #self.piece.selectednotes[:]
        for note in self.selectednotes:
            self.noteclipboard.append( [ note[0] - self.keymusic.cursorkeyindex - config.LOWESTnote,  #pitch
                                         note[1], #velocity
                                         note[2]-self.currentabsoluteticks, #absolute ticks
                                         note[3] # duration
                                       ] )
    
    def addquickchordinselection( self, text, midi ):
        if text:
            colonindex = text.find(";")
            if colonindex < 0:
                chordtext = text
                arptext = ""
            else:
                chordtext = text[0:colonindex]
                arptext = text[colonindex+1:]
                
            try:
                chordlist = CHORDS.from_shorthand(chordtext)
            except:
                self.setalert("onbekende chord.")
                chordlist = []
                
            if chordlist:
                for i in range(len(chordlist)):
                    chordlist[i] = NOTES.note_to_int(chordlist[i])
                chordlist = list(set(chordlist))
                chordlist.sort()
                
                tickmin, tickmax, midimin, midimax = self.getselectionregion()
                self.addchordinregion( chordlist, [tickmin,tickmax], [midimin,midimax], arptext ) 
                self.setcurrentticksandload( self.currentabsoluteticks )
                #self.anchor = 0
        self.setstate( state=self.NAVIGATIONstate )
        return {}

#### EDIT CLASS 

    def draw( self, screen ):
        if ( self.state == self.NAVIGATIONstate 
          or self.state == self.COMMANDstate or self.state == self.CHORDstate ):
            # draw the cursor if in one of those states:
            self.keymusic.setcursorheight( self.currentnoteticks*self.pixelspertick )

            if self.anchor:
                self.keymusic.setselectanchor( [ self.anchor[0], 
                    (self.anchor[1] - self.currentabsoluteticks)*self.pixelspertick ] )
            else:
                self.keymusic.setselectanchor( 0 )
        else:
            self.keymusic.setcursorheight( 0 )
            self.keymusic.setselectanchor( 0 )

        #backdrop screen
        self.backdrop.draw( screen )
        #draw keyboard and music
        self.keymusic.draw( screen )
        
        if self.preemptor:
            self.preemptor.draw( screen )
        elif self.state == self.COMMANDstate: 
            self.commander.draw( screen )
        elif self.state == self.CHORDstate: 
            self.chordcommander.draw( screen )

        if len(self.helperlines):
            #screenwidth, screenheight = screen.get_size()
            leftx = 10
            topy = 10 #0.1*screenheight
            self.helperlabelbox[0].left = leftx
            self.helperlabelbox[0].top = topy
            helperbgbox = Rect(leftx-5, topy-5, 
                               self.maxhelperwidth+10, 
                               len(self.helperlines)*self.helperlabelbox[0].height+10 )
            pygame.draw.rect( screen, self.helperbackcolor, helperbgbox )
            #pygame.draw.rect( screen, self.helperbackcolor,  self.helperlabelbox[0] )
            screen.blit( self.helperlabel[0], self.helperlabelbox[0] )
            for i in range(1,len(self.helperlines)):
                self.helperlabelbox[i].left = leftx
                self.helperlabelbox[i].top = self.helperlabelbox[i-1].bottom 
                #pygame.draw.rect( screen, self.helperbackcolor,  self.helperlabelbox[i] )
                screen.blit( self.helperlabel[i], self.helperlabelbox[i] )
        
        if self.alerttext:
            self.alertbox.top = 5
            self.alertbox.right = screen.get_width() - 5
            pygame.draw.rect( screen, self.helperbackcolor, self.alertbox ) 
            screen.blit( self.alert, self.alertbox ) 

#### END EDIT CLASS
