UPLOAD = 1
DOWNLOAD = 2
RECPACKAGE = 3
ACK = 4
DOWNLOADPACKAGE = 5

class Decoder:
    def isUpload(segment):
        return segment[0] == UPLOAD
    
    def isDownload(segment):
        return segment[0] == DOWNLOAD
    
    def isRecPackage(segment):
        return segment[0] == RECPACKAGE
    
    def isACK(segment):
        return segment[0] == ACK

    def isDownloadPackage(segment):
        return segment[0] == DOWNLOADPACKAGE

    # Msg = typeUpload + FileSize + FileName    
    def processUploadSegment(self, segment):  
        fileSize = int.from_bytes(segment[1:5], 'big')
        fileName = segment[5:].decode('utf-8')
        return fileSize, fileName

    # Msg = typeDownload + FileName
    def processDownloadSegment(self, segment):  
        return segment[1:].decode('utf-8')

    # Msg = typeRecPackage + sequenceNumber + Data
    def processRecPackageSegment(self, segment):
        sequenceNumber = int.from_bytes(segment[1:3], 'big')
        dataByte = segment[3:]
        return sequenceNumber, dataByte
    
    # Msg = typeRecPackage + sequenceNumber + Data
    def processDownloadPackageSegment(self, segment):
        sequenceNumber = int.from_bytes(segment[1:3], 'big')
        morePackages = bool.from_bytes(segment[3:4], 'big')
        dataByte = segment[4:]
        return sequenceNumber, morePackages, dataByte

    # Msg = typeACK + sequenceNumber
    def processACKSegment(self, segment):
        sequenceNumber = int.from_bytes(segment[1:], 'big')
        return sequenceNumber
    
    

  
    