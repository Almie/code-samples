from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
import os, subprocess, json
from . import dmxfile

ROOT_DIRECTORY = "F:\\Dropbox\\CG\\apex_treasurevid\\rnd\\example_shot_structure"
BLENDER_PATH = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe"

class StatusBarDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        item = index.internalPointer()

        painter.save()

        paddedRect = option.rect.marginsRemoved(QMargins(5,5,5,5))
        roundedRectPath = QPainterPath()
        roundedRectPath.addRoundedRect(paddedRect,5,5)
        pen = QPen(QColor('#FFFFFF'))
        painter.setPen(pen)
        painter.fillPath(roundedRectPath, QBrush(QColor("#13131a")))

        progressRect = option.rect
        progressRect.setWidth(progressRect.width()*item.progress)
        progressRectPath = QPainterPath()
        progressRectPath.addRect(progressRect)
        progressPath = roundedRectPath.intersected(progressRectPath)
        painter.fillPath(progressPath, QBrush(item.statusColor()))
        painter.drawPath(roundedRectPath)
        painter.drawText(paddedRect, Qt.AlignCenter, item.status())
        painter.restore()

class HeaderItem(object):
    def __init__(self):
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 5

    def row(self):
        return 0

    def data(self, column, role=Qt.DisplayRole):
        if not role == Qt.DisplayRole:
            return
        if column == 0:
            return "Scene"
        if column == 1:
            return "Shot"
        if column == 2:
            return "Rig"
        if column == 3:
            return "Frame Range"
        if column == 4:
            return "Status"
        if column == 5:
            return "" #Cache button

class ShotItem(object):
    def __init__(self, sceneName, shotName, shotDir, parent, rigs_config):
        self.parentItem = parent
        self.scene = sceneName
        self.shot = shotName
        self.shotDir = shotDir
        self.childItems = []
        self.rigsConfig = rigs_config
        self.checked = 0
        self.progress = 1
        self.caching = False

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return self.parentItem.columnCount()

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

    def data(self, column, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if column == 0:
                return self.scene
            if column == 1:
                return self.shot
            if column == 2:
                anims = len([c for c in self.childItems if c.dmxFile.dmxType != 'camera'])
                cameras = len([c for c in self.childItems if c.dmxFile.dmxType == 'camera'])
                return '{} animations, {} cameras'.format(anims, cameras)
            if column == 3:
                if self.childCount() == 0:
                    return ""
                startFrame = min([child.dmxFile.startFrame() for child in self.childItems])
                endFrame = max([child.dmxFile.endFrame() for child in self.childItems])
                return '{}-{}'.format(startFrame, endFrame)
        return

    def parent(self):
        return self.parentItem

    def populate(self):
        animDir = os.path.join(self.shotDir, 'anims')
        if not os.path.isdir(animDir):
            return
        for anim in os.listdir(animDir):
            print(os.path.splitext(anim), anim, self.shotDir)
            if os.path.splitext(anim)[-1] != ".dmx":
                continue
            charItem = CharItem(self.scene, self.shot, anim, self, self.rigsConfig)
            self.appendChild(charItem)

    def checkState(self):
        if self.childCount() == 0:
            return int(Qt.Unchecked)
        if all([self.child(row).checkState() == Qt.Checked for row in range(self.childCount())]):
            return int(Qt.Checked)
        elif any([self.child(row).checkState() == Qt.Checked for row in range(self.childCount())]):
            return int(Qt.PartiallyChecked)
        else:
            return int(Qt.Unchecked)

    def setChecked(self, state):
        if self.checkState() == Qt.PartiallyChecked and any(not(childItem.cachable()) for childItem in self.childItems):
            newState = Qt.Unchecked
        else:
            newState = state
        for childItem in self.childItems:
            if childItem.cachable():
                childItem.setChecked(newState)

    def cachable(self):
        return any([child.cachable() for child in self.childItems])

    def status(self):
        if self.caching:
            return "Caching - {:.1f}%".format(self.progress*100)
        if self.childCount() == 0:
            return "No animations"
        if any([child.status() == "MISSING RIG" for child in self.childItems]):
            return "MISSING RIG/S"
        if len([c for c in self.childItems if c.dmxFile.dmxType == 'camera']) == 0:
            return "No camera"
        if len([c for c in self.childItems if c.dmxFile.dmxType == 'camera']) > 1:
            return "?? Multiple Cameras ??"
        if all([child.status() == "Up to date" for child in self.childItems]):
            return "Up to date"
        return "Unknown"

    def statusColor(self):
        if self.caching:
            return QColor("#4287f5")
        if self.childCount() == 0:
            return QColor("#363636")
        if any([child.status() == "MISSING RIG" for child in self.childItems]):
            return QColor("#AA0000")
        if len([c for c in self.childItems if c.dmxFile.dmxType == 'camera']) == 0:
            return QColor("#db8709")
        if len([c for c in self.childItems if c.dmxFile.dmxType == 'camera']) > 1:
            return QColor("#ba1cd6")
        if all([child.status() == "Up to date" for child in self.childItems]):
            return QColor("#3aa816")
        return QColor("#ba1cd6")

    def getLatestMetaPath(self):
        version = 1
        metaFile = "{}_metadata_v{}.json".format(self.shot, version)
        metaPath = os.path.join(self.shotDir, 'metadata', metaFile)
        while os.path.isfile(metaPath):
            version += 1
            metaFile = "{}_metadata_v{}.json".format(self.shot, version)
            metaPath = os.path.join(self.shotDir, 'metadata', metaFile)
        return metaPath

    def getFrameRange(self):
        return min([int(child.dmxFile.startFrame()) for child in self.childItems]), max([int(child.dmxFile.endFrame()) for child in self.childItems])

    def getMetaDict(self):
        meta_dict = {}
        if self.childCount() > 0:
            meta_dict["start_frame"], meta_dict["end_frame"] = self.getFrameRange()
            delta = 0
            for shotItem in sorted(self.parentItem.childItems, key=lambda k: k.shot):
                if shotItem.scene != self.scene:
                    continue
                if shotItem == self:
                    break
                start_frame, end_frame = shotItem.getFrameRange()
                delta += end_frame - start_frame
            meta_dict["delta"] = delta
        return meta_dict

    def writeMetadata(self):
        metaPath = self.getLatestMetaPath()
        if not os.path.isdir(os.path.dirname(metaPath)):
            os.makedirs(os.path.dirname(metaPath))
        with open(metaPath, 'w') as f:
            json.dump(self.getMetaDict(), f)

class CharItem(object):
    ANIM_TYPE_CAMERA = 0
    ANIM_TYPE_CHARACTER = 1
    def __init__(self, sceneName, shotName, animName, parent, rigs_config):
        self.parentItem = parent
        self.animName = animName
        self.childItems = []

        self.rigsConfig = rigs_config

        self.dmxFilePath = os.path.join(parent.shotDir, 'anims', animName)
        self.dmxFile = dmxfile.DmxFile(self.dmxFilePath)

        self.checked = 0

        self.rigFile = ""
        if self.dmxFile.dmxType != "camera" and self.dmxFile.mdlPath() in self.rigsConfig:
            self.rigFile = self.rigsConfig[self.dmxFile.mdlPath()]
        if not self.dmxFile.mdlPath() in self.rigsConfig:
            print('No rig for {}'.format(self.dmxFile.mdlPath()))

        self.statusBar = None
        self.progress = 1
        self.caching = False
        self.loadingScene = False

        if self.status() in ["No cache", "Out of date"]:
            self.checked = Qt.Checked
        else:
            self.checked = Qt.Unchecked

    def child(self, row):
        return None

    def childCount(self):
        return 0

    def columnCount(self):
        return self.parentItem.columnCount()

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

    def parent(self):
        return self.parentItem

    def data(self, column, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if column == 0:
                return ""
            if column == 1:
                return self.animName
            if column == 2:
                return "camera" if self.dmxFile.dmxType == "camera" else self.rigFile or '<none>'
            if column == 3:
                return '{} ({})'.format(self.dmxFile.frameRange(), self.dmxFile.frameRate())
            if column == 4:
                return self.status()
        if role == Qt.ForegroundRole:
            white = QBrush(QColor("#FFFFFF"))
            if column == 2:
                return white if self.rigFile else QBrush(QColor("#FF0000"))
            if column == 4:
                return self.statusColor()
        return None

    def checkState(self):
        return self.checked

    def setChecked(self, state):
        self.checked = state

    @property
    def animType(self):
        if self.dmxFile.dmxType == "camera":
            return CharItem.ANIM_TYPE_CAMERA
        else:
            return CharItem.ANIM_TYPE_CHARACTER

    @property
    def cacheFileFormat(self):
        if self.animType == CharItem.ANIM_TYPE_CAMERA:
            return "fbx"
        else:
            return "abc"

    @property
    def rigName(self):
        if self.animType == CharItem.ANIM_TYPE_CAMERA:
            return "camera"
        multipleOfSameRig = any([child.rigFile == self.rigFile for child in self.parentItem.childItems if child != self])
        if multipleOfSameRig:
            return os.path.splitext(os.path.basename(self.rigFile))[0]+'_'+os.path.splitext(self.animName)[0]
        else:
            return os.path.splitext(os.path.basename(self.rigFile))[0]

    @property
    def cacheDir(self):
        if self.animType == CharItem.ANIM_TYPE_CAMERA:
            return os.path.join(self.parentItem.shotDir, 'camera')
        else:
            return os.path.join(self.parentItem.shotDir, 'alembics', self.rigName)

    @property
    def debugDir(self):
        if self.animType == CharItem.ANIM_TYPE_CAMERA:
            return os.path.join(self.parentItem.shotDir, 'debug', 'camera')
        else:
            return os.path.join(self.parentItem.shotDir, 'debug', 'alembics', self.rigName)

    @property
    def transformsDir(self):
        if self.animType != CharItem.ANIM_TYPE_CAMERA:
            return os.path.join(self.parentItem.shotDir, 'alembic_transforms', self.rigName)
        return None

    def getLatestCachePath(self, exists=True):
        if not self.rigFile and self.animType == CharItem.ANIM_TYPE_CHARACTER:
            return None
        if not os.path.isdir(self.cacheDir) and exists:
            return None
        version = 1
        cacheFile = "{}_{}_v{}.{}".format(self.parentItem.shot, self.rigName, version, self.cacheFileFormat)
        cachePath = os.path.join(self.cacheDir, cacheFile)
        while os.path.isfile(cachePath):
            version += 1
            cacheFile = "{}_{}_v{}.{}".format(self.parentItem.shot, self.rigName, version, self.cacheFileFormat)
            cachePath = os.path.join(self.cacheDir, cacheFile)
        if exists:
            version -= 1
            cacheFile = "{}_{}_v{}.{}".format(self.parentItem.shot, self.rigName, version, self.cacheFileFormat)
            cachePath = os.path.join(self.cacheDir, cacheFile)
            if not os.path.isfile(cachePath):
                return None
        return cachePath

    def isUpToDate(self):
        cachePath = self.getLatestCachePath()
        if not cachePath:
            return "No cache"
        cacheMTime = os.path.getmtime(cachePath)
        dmxMTime = os.path.getmtime(self.dmxFilePath)
        if cacheMTime > dmxMTime:
            return "Up to date"
        else:
            return "Out of date"

    def cachable(self):
        if self.status() != "MISSING RIG":
            return True
        return False

    def status(self):
        if not self.rigFile and self.dmxFile.dmxType != "camera":
            return "MISSING RIG"
        if self.caching:
            if self.loadingScene:
                return "Loading scene..."
            return "Caching - {:.1f}%".format(self.progress*100)
        else:
            return self.isUpToDate()

    def statusColor(self):
        if not self.rigFile and self.dmxFile.dmxType != "camera":
            return QColor("#AA0000")
        if self.caching:
            return QColor("#4287f5")
        else:
            upToDate = self.isUpToDate()
            if upToDate == "Up to date":
                return QColor("#3aa816")
            elif upToDate == "Out of date":
                return QColor("#dbb809")
            elif upToDate == "No cache":
                return QColor("#db8709")
        return QColor("#ba1cd6")

class ShotsFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, sourceModel=None):
        QSortFilterProxyModel.__init__(self)
        if sourceModel:
            self.setSourceModel(sourceModel)
        self.setDynamicSortFilter(True)

    def filterAcceptsRow(self, row, parent):
        return True
        #model = self.sourceModel()
        #index = model.index(row, 1, parent)
        #shotName = model.data(index, Qt.DisplayRole)
        #return "0010" in shotName

    def data(self, index, role):
        print("proxy data", index, role)
        QSortFilterProxyModel.data(self, index, role)

class ShotsTreeModel(QAbstractItemModel):
    def __init__(self, parent, rigs_config):
        QAbstractItemModel.__init__(self)
        self.treeView = parent
        self.shotItems = []
        self.rigsConfig = rigs_config
        self.rootItem = HeaderItem()

    def columnCount(self, parentIndex):
        return self.rootItem.columnCount()

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        if index.column() == 0:
            item = index.internalPointer()
            if not item.cachable():
                return Qt.ItemIsEnabled | Qt.ItemIsSelectable
            else:
                return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
        else:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def data(self, index, role):
        #print("main model data")
        if not index.isValid():
            return None

        if role == Qt.CheckStateRole and index.column() == 0:
            item = index.internalPointer()
            return int(item.checkState())
        if role == Qt.SizeHintRole:
            return QSize(0,30)
        if role == Qt.DisplayRole:
            item = index.internalPointer()
            return item.data(index.column())
        if role == Qt.ForegroundRole:
            item = index.internalPointer()
            return item.data(index.column(), Qt.ForegroundRole)

    def setData(self, index, value, role):
        if index.column() == 0 and role == Qt.CheckStateRole:
            item = index.internalPointer()
            item.setChecked(value)
            if item.childCount() > 0:
                bottomIndex = self.index(item.childCount()-1, 0, index)
            else:
                bottomIndex = index
            if item.parent() != self.rootItem:
                topIndex = self.parent(index)
            else:
                topIndex = index
            self.dataChanged.emit(topIndex, bottomIndex, Qt.CheckStateRole)
            return True

        return QAbstractItemModel.setData(self, index, value, role)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.rootItem.data(section)

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        if childItem == self.rootItem:
            return QModelIndex()

        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def populate(self, rootDir):
        for scene in os.listdir(rootDir):
            if scene == "blender_rigs":
                continue
            sceneDir = os.path.join(rootDir, scene)
            if not os.path.isdir(sceneDir):
                continue
            for shot in os.listdir(sceneDir):
                shotDir = os.path.join(sceneDir, shot)
                if not os.path.isdir(shotDir):
                    continue
                shotItem = ShotItem(scene, shot, shotDir, self.rootItem, self.rigsConfig)
                shotItem.populate()
                self.rootItem.appendChild(shotItem)

    def clear(self):
        self.beginResetModel()
        del self.rootItem
        self.rootItem = HeaderItem()
        self.endResetModel()

class ShotsView(QTreeView):
    def __init__(self, parent, rootDir, rigs_config):
        QTreeView.__init__(self, parent)
        self.rootDir = rootDir
        self.dataModel = ShotsTreeModel(self, rigs_config)
        self.proxyModel = ShotsFilterProxyModel(self.dataModel)
        self.setModel(self.dataModel)

        self.statusBarDelegate = StatusBarDelegate()
        self.setItemDelegateForColumn(4, self.statusBarDelegate)

        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.header().setSectionResizeMode(4, QHeaderView.Fixed)
        self.header().resizeSection(0, 75)
        self.header().resizeSection(3, 125)
        self.header().resizeSection(4, 200)

        self.dataModel.populate(rootDir)
        self.proxyModel.invalidateFilter()

    def setRootDir(self, newRootDir):
        self.rootDir = newRootDir
        self.refresh()

    def refresh(self):
        self.dataModel.clear()
        self.dataModel.populate(self.rootDir)

class CacherMainWindow(QMainWindow):
    def __init__(self, rigs_config={}):
        QMainWindow.__init__(self)
        self.setWindowTitle("SFM To Blender Cacher")

        self.rigsConfig = rigs_config
        self.vl = QVBoxLayout(self)
        self.mainWidget = QWidget(self)
        self.mainWidget.setLayout(self.vl)
        self.setCentralWidget(self.mainWidget)

        self.rootDirRow = QWidget(self)
        self.rootDirHl = QHBoxLayout(self)
        self.rootDirRow.setLayout(self.rootDirHl)
        self.vl.addWidget(self.rootDirRow)

        self.rootDirLabel = QLabel("Root Directory: ", self)
        self.rootDirHl.addWidget(self.rootDirLabel)
        self.rootDirEdit = QLineEdit(ROOT_DIRECTORY, self)
        self.rootDirHl.addWidget(self.rootDirEdit)
        self.rootDirBrowseBtn = QPushButton("Browse", self)
        self.rootDirBrowseBtn.clicked.connect(self.rootDirBrowse)
        self.rootDirHl.addWidget(self.rootDirBrowseBtn)
        self.rootDirRefreshBtn = QPushButton("Refresh", self)
        self.rootDirRefreshBtn.clicked.connect(self.rootDirRefresh)
        self.rootDirHl.addWidget(self.rootDirRefreshBtn)

        self.settingsRow = QWidget(self)
        self.settingsRowHl = QHBoxLayout(self)
        self.settingsRow.setLayout(self.settingsRowHl)
        self.vl.addWidget(self.settingsRow)

        self.debugCheckBox = QCheckBox("Save debug scene", self)
        self.settingsRowHl.addWidget(self.debugCheckBox)
        self.transformsCheckBox = QCheckBox("Output alembic transforms", self)
        self.settingsRowHl.addWidget(self.transformsCheckBox)

        self.shotsView = ShotsView(self, ROOT_DIRECTORY, rigs_config)
        self.vl.addWidget(self.shotsView)

        self.bottomRow = QWidget(self)
        self.bottomRowHl = QHBoxLayout(self)
        self.bottomRow.setLayout(self.bottomRowHl)
        self.vl.addWidget(self.bottomRow)

        self.uncheckAllBtn = QPushButton("Uncheck All", self)
        self.uncheckAllBtn.clicked.connect(self.uncheckAll)
        self.bottomRowHl.addWidget(self.uncheckAllBtn)
        self.createDirsBtn = QPushButton("Create Shot Directories", self)
        self.createDirsBtn.clicked.connect(self.createShotDirs)
        self.bottomRowHl.addWidget(self.createDirsBtn)
        self.updateMetaBtn = QPushButton("Update Metadata", self)
        self.updateMetaBtn.clicked.connect(self.updateMetadata)
        self.bottomRowHl.addWidget(self.updateMetaBtn)
        self.cacheBtn = QPushButton("Cache Selected", self)
        self.cacheBtn.clicked.connect(self.cache)
        self.bottomRowHl.addWidget(self.cacheBtn)

        self.resize(1280, 800)

    def uncheckAll(self):
        for shotItem in self.shotsView.dataModel.rootItem.childItems:
            shotItem.setChecked(Qt.Unchecked)

    def checkAll(self):
        for shotItem in self.shotsView.dataModel.rootItem.childItems:
            if shotItem.checkState() == Qt.PartiallyChecked:
                shotItem.setChecked(Qt.Unchecked)
            shotItem.setChecked(Qt.Checked)

    def rootDirRefresh(self):
        rootDir = self.rootDirEdit.text()
        self.shotsView.setRootDir(rootDir)

    def rootDirBrowse(self):
        rootDir = QFileDialog.getExistingDirectory(self, "Choose Root Directory", self.rootDirEdit.text())
        if rootDir:
            self.rootDirEdit.setText(rootDir)
            self.rootDirRefresh()

    def createShotDirs(self):
        rootDir = self.rootDirEdit.text()
        if not os.path.isdir(rootDir):
            ok = QMessageBox.error(self, "Error!", "Current root directory is not valid. Choose a valid root directory before proceeding.")
            return None
        jsonFile, ok = QFileDialog.getOpenFileName(self, "Choose JSON shot list file", filter="JSON Files (*.json)")
        if ok and jsonFile:
            sequenceName, sq_ok = QInputDialog.getText(self, "Sequence Name", "Choose Sequence Name: ", text=os.path.splitext(os.path.basename(jsonFile))[0])
            if sq_ok and sequenceName:
                sq_path = os.path.join(rootDir, sequenceName)
                if not os.path.isdir(sq_path):
                    os.mkdir(sq_path)
                with open(jsonFile, 'r') as f:
                    shotList = json.load(f)
                for shot in shotList:
                    shotDir = os.path.join(sq_path, shot["name"])
                    if not os.path.isdir(shotDir):
                        os.mkdir(shotDir)
                    subDirs = ["anims", "alembics", "camera", "metadata"]
                    for subDir in subDirs:
                        subDirPath = os.path.join(shotDir, subDir)
                        if not os.path.isdir(subDirPath):
                            os.mkdir(subDirPath)
                self.shotsView.refresh()

    def updateMetadata(self):
        print('updating metadata...')

        for row in range(self.shotsView.dataModel.rowCount()):
            shotItem = self.shotsView.dataModel.rootItem.child(row)
            if not any([shotItem.child(row).checkState() == Qt.Checked for row in range(shotItem.childCount())]):
                continue
            shotItem.writeMetadata()

    def cache(self):
        print('caching...')
        rootDir = self.rootDirEdit.text()
        saveDebug = self.debugCheckBox.checkState() == Qt.Checked
        saveTransforms = self.transformsCheckBox.checkState() == Qt.Checked
        totalShots = 0
        totalAnims = 0

        for row in range(self.shotsView.dataModel.rowCount()):
            shotItem = self.shotsView.dataModel.rootItem.child(row)
            if not any([shotItem.child(row).checkState() == Qt.Checked for row in range(shotItem.childCount())]):
                continue
            shotIndex = self.shotsView.dataModel.index(row, 4, QModelIndex())
            shotItem.caching = True
            shotItem.progress = 0
            shotItem.writeMetadata()
            charsCached = 0
            checkedCount = len([child for child in shotItem.childItems if child.checkState() == Qt.Checked])
            for charRow in range(shotItem.childCount()):
                charItem = shotItem.child(charRow)
                if not charItem.checkState() == Qt.Checked:
                    continue
                charIndex = self.shotsView.dataModel.index(charRow, 4, shotIndex)
                charItem.caching = True
                charItem.loadingScene = True
                charItem.progress = 0
                self.shotsView.dataModel.dataChanged.emit(shotIndex, charIndex, Qt.DisplayRole)
                rigPath = os.path.join(rootDir, charItem.rigFile)
                cachePath = charItem.getLatestCachePath(exists=False)
                print(cachePath)
                if not cachePath:
                    continue
                dmxPath = charItem.dmxFile.filepath
                startFrame = charItem.dmxFile.startFrame()
                endFrame = charItem.dmxFile.endFrame()
                if charItem.dmxFile.dmxType != 'camera':
                    pythonScriptPath = os.path.join(os.path.dirname(__file__), 'cache\\alembic.py')
                    cmds = [BLENDER_PATH, rigPath, '--background', '--frame-start', startFrame, '--frame-end', endFrame, '--python', pythonScriptPath, '--', 'anim-path', dmxPath, 'export-path', cachePath]
                    if saveTransforms:
                        transformsPath  = os.path.join(charItem.transformsDir, '.'.join(list(os.path.splitext(os.path.basename(cachePath))[:-1])+["fbx"]))
                        print('outputting alembic transforms to: {}'.format(transformsPath))
                        cmds.extend(['--transforms', transformsPath])
                    if saveDebug:
                        debugPath = os.path.join(charItem.debugDir, '.'.join(list(os.path.splitext(os.path.basename(cachePath))[:-1])+["blend"]))
                        print('saving debug scene to: {}'.format(debugPath))
                        cmds.extend(['--debug', debugPath])
                    cacheProc = subprocess.Popen(cmds, stdout=subprocess.PIPE, bufsize=1)
                    while True:
                        line = cacheProc.stdout.readline()
                        if not line:
                            break
                        line = line.decode('UTF-8')
                        print(line, line.strip())
                        if line.startswith('Caching Animation'):
                            charItem.loadingScene = False
                            cachedFrames = float(line.split('|')[1])
                            totalFrames = float(line.split('|')[2])
                            print(cachedFrames/totalFrames)
                            charItem.progress = cachedFrames/totalFrames
                            shotItem.progress = float(charsCached)/checkedCount+charItem.progress/checkedCount
                            self.shotsView.dataModel.dataChanged.emit(shotIndex, charIndex, Qt.DisplayRole)
                        QApplication.processEvents()
                else:
                    pythonScriptPath = os.path.join(os.path.dirname(__file__), 'cache\\camera.py')
                    cmds = [BLENDER_PATH, '--background', '--frame-start', startFrame, '--frame-end', endFrame, '--python', pythonScriptPath, '--', 'anim-path', dmxPath, 'export-path', cachePath, 'shot-name', shotItem.shot]
                    if saveDebug:
                        debugPath = os.path.join(charItem.debugDir, '.'.join(list(os.path.splitext(os.path.basename(cachePath))[:-1])+["blend"]))
                        print('saving debug scene to: {}'.format(debugPath))
                        cmds.extend(['--debug', debugPath])
                    cacheProc = subprocess.Popen(cmds)
                    result = cacheProc.communicate()
                    charItem.loadingScene = False
                charItem.progress = 1
                charItem.caching = False
                shotItem.progress = float(charRow+1)/checkedCount
                totalAnims += 1
                charsCached += 1
                self.shotsView.dataModel.dataChanged.emit(shotIndex, charIndex, Qt.DisplayRole)
            shotItem.caching = False
            shotItem.progress = 1
            totalShots += 1
        ok = QMessageBox.information(self, "Caching Finished", "Finished caching {} animations in {} shots.".format(totalAnims, totalShots), QMessageBox.Ok)
