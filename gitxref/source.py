import hashlib
from collections import defaultdict

from bitarray import bitarray
from tqdm import tqdm

from gitxref.bitmaps import Bitmaps


def hashblob(f):
    h = hashlib.sha1()
    h.update(b'blob %d\0' % f.stat().st_size)
    h.update(f.read_bytes())
    return h.digest()

def bitarray_zero(length):
    b = bitarray(length, endian='big')
    b[:] = False
    return b


def bitarray_defaultdict(length):
    return defaultdict(lambda: bitarray_zero(length))


class Source(object):

    def __init__(self, repo, directory, backrefs):
        self.repo = repo
        self.directory = directory
        self.backrefs = backrefs
        self.blobs = set()
        self.paths = {}

        for f in directory.rglob('*'):
            path = f.relative_to(directory)
            if f.is_file() and not f.is_symlink():
                binsha = hashblob(f)
                self.blobs.add(binsha)
                self.paths[binsha] = str(path)

        self.blobs = list(self.blobs)

        self.blob_index = {k:v for v,k in enumerate(self.blobs)}

    def find_backrefs(self):
        self.commits = bitarray_defaultdict(len(self.blobs))
        for index, binsha in tqdm(enumerate(self.blobs), unit='blob', desc='Building bitmaps', total=len(self.blobs)):
            for c in self.backrefs.commits_for_object(binsha):
                self.commits[c][index] = True

    def make_bitmaps(self, processes=None):
        with Bitmaps(self.repo, processes=processes) as bm:
            self.commits = bm.build(self.blob_index)

    def find_best(self):
        unfound = bitarray(len(self.blobs))
        unfound[:] = True

        best = sorted(self.commits.items(), key=lambda x: sum(x[1]&unfound), reverse=True)

        while len(best):
            yield (best[0][0], best[0][1]&unfound)
            unfound &= ~best[0][1]

            # old way - evaluates sum(x[1]&unfound) twice
            best = list(filter(lambda x: sum(x[1]&unfound) > 0, best[1:]))
            best.sort(key=lambda x: sum(x[1]&unfound), reverse=True)

            # new
            #d = ((sum(x[1]&unfound), x) for x in best[1:])
            #s = sorted(filter(lambda x: x[0] > 0, d))
            #best = [x[1] for x in s]




        yield (None, unfound)
        return

    def __getitem__(self, arg):
        if type(arg) == int:
            return (self.blobs[arg], self.paths[self.blobs[arg]])
        else:
            yield from ((self.blobs[x], self.paths[self.blobs[x]]) for x,t in enumerate(arg[:len(self.blobs)]) if t)
