class MessageProcessor:

    # Msg = typeUpload + FileSize + FileName    
    def processUploadSegment(self, segment):  
        fileSize = int.from_bytes(segment[1:5], 'big')
        fileNameArray = segment[5:9]
        fileName = ""
        for i in range(0,4):
            fileName += chr(fileNameArray[i])
        return fileSize, fileName

    # Msg = typeDownload + FileName
    def processDownloadSegment(self, segment):  
        fileNameArray = segment[1:5]
        fileName = ""
        for i in range(0,4):
            fileName += chr(fileNameArray[i])
        return fileName

    # Msg = typeRecPackage + sequenceNumber + CheckSum + Data
    def processRecPackageSegment(self, segment):
        sequenceNumber = int.from_bytes(segment[1:3], 'big')
        checkSum = int.from_bytes(segment[3:5], 'big')
        dataByte = segment[5:]
        data = ""
        for i in range(0, len(dataByte)):
            data += chr(dataByte[i])
        return sequenceNumber, checkSum, data
    
    # Msg = typeACK + sequenceNumber
    def processACKSegment(self, segment):
        sequenceNumber = int.from_bytes(segment[1:], 'big')
        return sequenceNumber
    


  
    