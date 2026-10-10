"""Check approved indicators using real local-game moves and keyboard input."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'))
sys.path.insert(0,str(root/'assets/scripts'))
from screenshot import Session
from build_graphics import square_image,PIECES,blit
from palette import rgb
rom=next(p for p in [root.parent/'emulator/rom.bin',root.parent/'emulator-win/rom.bin'] if p.exists())
s=Session(root.parent/'x16-emulator/build/x16emu',rom)
try:
    s.emu.advance(480)
    s.press('n');s.emu.advance(300)
    s.press('Left');s.press('Return');s.emu.advance(300)
    s.click(276,372);s.click(276,260) # e2-e4
    s.click(220,92);s.click(220,204) # d7-d5
    s.click(276,260) # select e4, with e5 move and d5 capture
    s.move_mouse(639,479)
    path=root/'build/indicators-selected.png'
    s.shot(path)
    actual=np.asarray(Image.open(path).convert('RGB'))
    palette=np.array([rgb(i) for i in range(16)],np.uint8)
    for x,y,state,piece,light in [(248,232,'SELECTED',0,True),(248,176,'TARGET',None,False),(192,176,'CAPTURE',6,True)]:
        expected=square_image('NEWSPRINT',light,state)
        if piece is not None:blit(expected,0,0,PIECES[:,piece*56:(piece+1)*56])
        np.testing.assert_array_equal(actual[y:y+56,x:x+56],palette[expected])
    # Move keyboard focus onto the selected piece; the exact approved 64px
    # cursor sprite must remain within the palette and be red, not alert red.
    s.press('Right');s.press('Left')
    s.move_mouse(639,479)
    s.shot(root/'build/indicators-keyboard.png')
    attrs=s.emu.read_memory(0x1FC08,8,space='vram')
    assert attrs[6]==12
    sprite=s.emu.read_memory(0x1D100,2048,space='vram')
    assert set(v for b in sprite for v in (b>>4,b&15))=={0,2,7}
    print('PASS: actual selection, legal move, capture pixels and keyboard sprite match approved markers; no yellow selection fill')
finally:s.close()
