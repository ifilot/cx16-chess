"""Create a FAT32 SD image of the distribution for real CMDR-DOS tests.

Requires dosfstools (mkfs.fat) and mtools (mcopy). Does not touch physical disks.
"""
from pathlib import Path
import struct
import subprocess
from package_graphics import ROOT


def main():
    folder = ROOT / 'build/dist/CHESS'
    image = ROOT / 'build/dist/CHESS.IMG'
    sectors, start = 131072, 2048  # 64 MiB card, partition starts at 1 MiB
    mbr = bytearray(512)
    mbr[446:462] = struct.pack('<B3sB3sII', 0, b'\xfe\xff\xff', 0x0c,
                              b'\xfe\xff\xff', start, sectors - start)
    mbr[510:512] = b'\x55\xaa'
    with image.open('wb') as file:
        file.truncate(sectors * 512)
        file.write(mbr)
    subprocess.run(['mkfs.fat', '-F', '32', '--offset', str(start), str(image)], check=True)
    subprocess.run(['mcopy', '-i', str(image) + '@@' + str(start * 512),
                    *(str(path) for path in sorted(folder.iterdir())), '::'], check=True)
    print(f'SD image: {image}')


if __name__ == '__main__':
    main()
