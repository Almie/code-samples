from . import datamodel #3rd party library for reading the DMX file format

class DmxFile(object):
    def __init__(self, filepath):
        self.filepath = filepath
        self.dm = datamodel.load(filepath)
        if self.dm.root.get('camera'):
            self.dmxType = 'camera'
        else:
            self.dmxType = 'character'

    def mdlPath(self):
        return self.dm.root["exportTags"].get('mdl')

    def frameRange(self):
        return self.dm.root["exportTags"]["frameRange"].split('x')[0]

    def frameRate(self):
        return self.dm.root["exportTags"]["frameRate"]

    def startFrame(self):
        return self.frameRange().split('-')[-2]

    def endFrame(self):
        return self.frameRange().split('-')[-1]
