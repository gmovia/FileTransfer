from socketUDP import SocketUDP
from protocol import Protocol

UPLOAD = 1
DOWNLOAD = 2
RECPACKAGE = 3

def main():
    serverSocket = SocketUDP()
    serverSocket.bindSocket("localhost", 12000)
    protocol = Protocol()
    fileDownload = ""

    while True:
        
        segment, clientAddress = protocol.receive(serverSocket)
        command = segment[0]

        if command == UPLOAD:
            fileSize, fileName = protocol.processUploadSegment(segment)
            print('command {} fileSize {} fileName {}'.format(command, fileSize, fileName))
        
        elif command == DOWNLOAD:
            fileName = protocol.processDownloadSegment(segment)
            print('command {} fileName {}'.format(command, fileName))
        
        elif command == RECPACKAGE:
            sequenceNumber, checkSum, data = protocol.processRecPackageSegment(segment)
            if not (protocol.verifyCheckSum(checkSum, data)):
                exit()
            
            print('Sequence number {}'.format(sequenceNumber))

            ACKMessage = protocol.createACKMessage(sequenceNumber)
            protocol.sendMessage(serverSocket, clientAddress, ACKMessage)

            fileDownload += data
            if(len(fileDownload) == fileSize):
                print('file {}'.format(fileDownload))
                fileDownload = ""

main()