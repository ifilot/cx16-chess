# Chess pieces

`svg/` holds the "Cburnett" chess pieces by Colin M.L. Burnett, downloaded
from Wikimedia Commons (`Chess_{p,n,b,r,q,k}{l,d}t45.svg`). They are
triple-licensed under the GFDL, BSD and GPL licenses.

`pieces.png` is generated from them by `assets/scripts/make_sources.py`:
each 45x45 SVG is supersampled and thresholded into two-colour pixel art
(white pieces with a 2.0 stroke, black pieces with the original 1.5 stroke)
on a 48x48 cell. The PNG is the source the build uses, so it can be touched
up by hand.
