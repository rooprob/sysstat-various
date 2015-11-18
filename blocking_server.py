
from socket import *
import time

HOST = ''
PORT = 29876
ADDR = (HOST,PORT)
BUFSIZE = 4096

serv = socket(AF_INET, SOCK_STREAM)

running = True

serv.bind((ADDR))
serv.listen(128)
while running is True:
    conn,addr = serv.accept() #accept the connection
    print '...connected!'
    conn.send('TEST')
    conn.close()

