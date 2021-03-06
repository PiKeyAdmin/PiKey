# backdrops.py - achtergronden en backdrops
from metagame import *
import config

class ColorOscillatingBackDropClass( BackDropClass ):
    def __init__( self, **kwargs ):
        self.image = 0
        self.allowedchanges = [  "redphase",
                                "greenphase",
                                "bluephase" ]

        self.redphase = 0.1

        self.greenphase = 0.1
 
        self.bluephase = 0.1

        self.setstate( **kwargs )

    def update( self, dt ):
        self.red = 2 * (self.redphase )
        self.green = 2* ( self.greenphase )
        self.blue = 2 * ( self.bluephase )

    def draw( self, screen ):
        screen.fill( (self.red,self.green,self.blue) )
        self.drawimage( screen )

class LeftPianoKeyClass( PianoKeyClass ):
    ''' deze key is anchored links met x en rechts met y '''
    def draw( self, screen, x, y ):
        pos = Rect(0,0,self.length,self.width) # lengte is de langste stukje 
        pos.left = x
        pos.centery = y 
        pygame.draw.rect( screen, self.fillcolor, pos ) #draw filled

class LeftPianoBackDropClass( ColorOscillatingBackDropClass ):
    ''' this backdrop has a piano on the left-side of the screen '''
#### CLASS LEFTPIANO
    def __init__( self, **kwargs ):
        ColorOscillatingBackDropClass.__init__(self, **kwargs)

        self.allowedchanges = [ "redphase",
                                "greenphase",
                                "bluephase" ]

        self.whitekeyfractions = [ 1.0/7 ] * 7  # height of each white key, 
                                                # as a fraction of the screen's vertical height
        ## make 12 keys
        self.keys = []
        for i in range(12):
            ## make the on colors of the keys a rainbow
            if i in [ 0, 2, 4, 5, 7, 9, 11 ]:  
                #white keys
                self.keys.append( LeftPianoKeyClass( fillcoloroff=(200,200,200), length=130,
                            fillcoloron=config.rainbow[i] ) )
            else: 
                #black keys
                self.keys.append( LeftPianoKeyClass( fillcoloroff=(20,20,20), length=80,
                            fillcoloron=config.rainbow[i] ) )

#### CLASS LEFTPIANO
    def setstate( self, **kwargs ):
        for key, value in kwargs.iteritems():
            if key in self.allowedchanges: 
                setattr( self, key, value )
            else:
                Warn("in LeftPianoBackDropClass:setstate - key "+ key +" is protected!!") 

#### CLASS LEFTPIANO
    def hitrandomkey( self, midi, midioctave=5, notevel=100 ): # midioctave = 5 is middle C
        randompiano = int( random()*12 )
        self.setstate( redphase=randomphase(), 
                       greenphase=randomphase(), 
                       bluephase=randomphase() )
        ## and play it with midi:
        self.hitkey( midi, randompiano + midioctave*12, notevel )

#### CLASS LEFTPIANO
    def brightenkey( self, midinote = 60, notevel = 100 ): # midinote = 60 is middle C
        self.keys[ midinote % 12 ].setstate( on=notevel )

#### CLASS LEFTPIANO
    def hitkey( self, midi, midinote = 60, notevel = 100 ): # midinote = 60 is middle C
        # highlight of flash de key aan
        self.brightenkey( midinote, notevel )
        ## speel het met midi:
        midi.playnote( midinote )

#### CLASS LEFTPIANO
    def update( self, dt ):
        ColorOscillatingBackDropClass.update(self, dt)
        for key in self.keys:
            key.update(dt)

#### CLASS LEFTPIANO
    def draw( self, screen ):
        ColorOscillatingBackDropClass.draw(self, screen)
        screenwidth, screenheight = screen.get_size()
        whitekeylength = 0.15*screenwidth
        blackkeylength = 0.10*screenwidth
        iwhite=0
        middleofnote = screenheight + 0.5*screenheight*self.whitekeyfractions[0]
        middles = [ ]
        for i in [ 0, 2, 4, 5, 7, 9, 11 ]:  # white keys
            middleofnote -= screenheight*self.whitekeyfractions[iwhite] 
            middles.append( middleofnote ) 
            self.keys[i].setstate( width=0.4*screenheight*self.whitekeyfractions[iwhite],
                                   length=whitekeylength )
            self.keys[i].draw( screen, 0, middleofnote )
            iwhite += 1

        iwhite = 0
        for i in [ 1, 3, 6, 8, 10 ]: # black keys
            self.keys[i].setstate( width=0.18*screenheight*(self.whitekeyfractions[iwhite]
                                                             +self.whitekeyfractions[iwhite+1]),
                                   length=blackkeylength )
            self.keys[i].draw( screen, 0, 0.5*(middles[iwhite]+middles[iwhite+1]) )
            iwhite += 1
            if i == 3:
                iwhite += 1
        
        self.drawimage( screen )

