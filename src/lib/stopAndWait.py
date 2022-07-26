import queue
import logging
from lib.protocol import Protocol
from lib.fileHandler import FileHandler
from lib.decoder import Decoder
from lib.encoder import Encoder
from socket import timeout
from math import ceil

MSS = 5
N_TIMEOUTS = 20
FINAL_ACK_TRIES = 5

class StopAndWait:

    def __init__(self) -> None:
        self.protocol = Protocol()
        

    def sendAndReceiveACK(self, msg, addr, recvQueue, sendQueue):
        timeouts = 0
        while True:
            try:
                sendQueue.put((msg, addr))
                segment = recvQueue.get(block=True, timeout=1)
                if Decoder.isTerminate(segment):
                    raise Exception('Closed server')
                # que pasa si se recibe un paquete que no es ACK? deberia saltar excepcion en el decoder
                sequenceNumber = self.protocol.processACKSegment(segment)
                logging.debug(f'Download {addr}: recibido ACK {sequenceNumber}')
                break
            except queue.Empty:
                timeouts += 1
                if timeouts >= N_TIMEOUTS:
                    logging.warning('Timeout exceeded')
                    raise Exception('Timeouts exceeded')
                logging.debug("timeout, no se recibe el ACK. Se reenvia el paquete") 
        return sequenceNumber
 
    def socketSendAndReceiveACK(self, msg, serverAddr, clientSocket):
        clientSocket.resetTimeouts()
        while True:
            try:
                clientSocket.setTimeOut(1) 
                self.protocol.sendMessage(clientSocket, serverAddr, msg)
                segment, _ = self.protocol.receive(clientSocket)
                sequenceNumber = self.protocol.processACKSegment(segment)
                break
            except timeout:
                clientSocket.addTimeOut()
                logging.debug("timeout, no se recibe el ACK. Se envia nuevamente la data") 
        return sequenceNumber    

    def socketSendAndReceiveFileSize(self, msg, serverAddr, clientSocket):
        clientSocket.resetTimeouts()
        while True:
            try:
                clientSocket.setTimeOut(1) 
                self.protocol.sendMessage(clientSocket, serverAddr, msg)
                segment, _ = self.protocol.receive(clientSocket)
                break
            except timeout:
                clientSocket.addTimeOut()
                logging.debug("timeout, no se recibe el filesize. Se envia nuevamente el mensaje inicial") 
        return segment    


    def sendAndReceiveData(self, msg, serverAddr, clientSocket):
        while True:
            try:
                clientSocket.setTimeOut(1) 
                self.protocol.sendMessage(clientSocket, serverAddr, msg)
                segment, _ = self.protocol.receive(clientSocket)
                sequenceNumber, morePackages, data = self.protocol.processDownloadPackageSegment(segment)
                break
            except timeout:
                clientSocket.addTimeOut()
                logging.debug("timeout, no se recibe el DownloadPackage. Se envia nuevamente el paquete inicial") 
        return sequenceNumber, morePackages, data        

    
    def clientUpload(self, clientSocket, fileName, file, fileSize, serverAddr):

        uploadMessage = self.protocol.createUploadMessage(fileSize, fileName)
        sequenceNumber = self.socketSendAndReceiveACK(uploadMessage, serverAddr, clientSocket)

        uploaded = 0
        while uploaded < fileSize:
            data = FileHandler.readFileBytes(uploaded, file, MSS)
            packageMessage = self.protocol.createRecPackageMessage(data, sequenceNumber+1)
            sequenceNumber = self.socketSendAndReceiveACK(packageMessage, serverAddr, clientSocket)
            logging.debug(f'Recibe ACK = {sequenceNumber}')
            uploaded += min(len(data), MSS)
        logging.info("Upload finished")


    def clientDownload(self, clientSocket, fileName, path, serverAddr):
        
        file = FileHandler.newFile(str(path), fileName)
        
        downloadMessage = self.protocol.createDownloadMessage(fileName)
        prevSequenceNumber, morePackages, data = self.sendAndReceiveData(downloadMessage, serverAddr, clientSocket)
        logging.debug('Recibe Sequence number = {}, data = {}'.format(prevSequenceNumber, data))
        file.write(data)
        ACKMessage = self.protocol.createACKMessage(prevSequenceNumber)
        self.protocol.sendMessage(clientSocket, serverAddr, ACKMessage)
        
        while morePackages:
            clientSocket.setTimeOut(15)
            segment, serverAddr = self.protocol.receive(clientSocket)
            sequenceNumber, morePackages, data = self.protocol.processDownloadPackageSegment(segment)
            logging.debug('Recibe Sequence number = {}, data = {}'.format(sequenceNumber, data))
            ACKMessage = self.protocol.createACKMessage(sequenceNumber)
            self.protocol.sendMessage(clientSocket, serverAddr, ACKMessage)

            if sequenceNumber > prevSequenceNumber:
                file.write(data)
            prevSequenceNumber = sequenceNumber

        for _ in range(FINAL_ACK_TRIES):    
            self.protocol.sendMessage(clientSocket, serverAddr, ACKMessage)
    
        FileHandler.closeFile(file)
        logging.info("Download finished")


    def serverUpload(self, recvQueue, sendQueue, clientAddr, dstPath):
        segment = recvQueue.get()
        fileSize, fileName = self.protocol.processUploadSegment(segment)
        file = FileHandler.newFile(dstPath, fileName)
        
        ACKMessage = self.protocol.createACKMessage(0)
        sendQueue.put((ACKMessage, clientAddr))
        logging.debug('command {} fileSize {} fileName {}'.format(segment[0], fileSize, fileName))
        
        transferred = 0
        prevSequenceNumber = 0
        while transferred != fileSize:

            try:
                segment = recvQueue.get(block=True, timeout=15)
            except:
                logging.debug(f'Timeouts exceeded: ending thread {clientAddr}...')
                return
            if Decoder.isRecPackage(segment):            
                sequenceNumber, data = self.protocol.processRecPackageSegment(segment)
                logging.debug(f'Upload {clientAddr}: Recibe paquete de datos con sequence number {sequenceNumber}')

                ACKMessage = self.protocol.createACKMessage(sequenceNumber)
                sendQueue.put((ACKMessage, clientAddr))

                if sequenceNumber > prevSequenceNumber:
                    transferred += len(data)
                    file.write(data)
                prevSequenceNumber = sequenceNumber
            elif Decoder.isUpload(segment):
                sendQueue.put((ACKMessage, clientAddr))
            elif Decoder.isTerminate(segment):
                logging.debug(f'Closed server: ending thread {clientAddr}...')
                return

        terminateMsg = Encoder.createTerminateMessage()
        sendQueue.put((terminateMsg, clientAddr))

        for _ in range(FINAL_ACK_TRIES):    
            sendQueue.put((ACKMessage, clientAddr))

        FileHandler.closeFile(file)
        logging.info(f'Upload from {clientAddr} finished')               



    def serverDownload(self, recvQueue, sendQueue, clientAddr, dstPath):
        segment = recvQueue.get()
        fileName = self.protocol.processDownloadSegment(segment)

        logging.debug('command {} fileName {}'.format(segment[0], fileName))
        path = dstPath + fileName
        try:
            file = FileHandler.openFile(path)
            fileSize = FileHandler.getFileSize(path)
        except:
            logging.debug('File not found')
            return

        numPackages = ceil(fileSize / MSS)
        sequenceNumber = 0
        sent = 0
        morePackages = True
        while sent < fileSize:
            data = FileHandler.readFileBytes(sent, file, MSS)
            sent += min(len(data), MSS)
            morePackages = numPackages > 1
            packageMessage = self.protocol.createDownloadPackageMessage(data, sequenceNumber+1, morePackages)
            logging.debug(f'Download {clientAddr}: se envia el paquete {sequenceNumber+1}')
            try:
                sequenceNumber = self.sendAndReceiveACK(packageMessage, clientAddr, recvQueue, sendQueue)
            except Exception as e:
                logging.debug(f'{e}: ending thread {clientAddr}...')
                return
            numPackages -= 1

        terminateMsg = Encoder.createTerminateMessage()
        sendQueue.put((terminateMsg, clientAddr))

        FileHandler.closeFile(file)
        logging.info(f'Download from {clientAddr} finished')               
