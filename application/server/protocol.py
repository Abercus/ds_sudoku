# Setup Python logging --------------------------------------------------------
import logging
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG,format=FORMAT)
LOG = logging.getLogger()
# Imports----------------------------------------------------------------------
from exceptions import ValueError # for handling number format exceptions
from application.common import RSP_BADFORMAT, PUSH_TIMEOUT,\
	MSG_FIELD_SEP, MSG_SEP, RSP_OK, RSP_UNAME_TAKEN, RSP_SESSION_ENDED,\
	RSP_SESSION_TAKEN, RSP_UNKNCONTROL,\
	REQ_UNAME, REQ_GET_SESS, REQ_JOIN_SESS, REQ_NEW_SESS,\
	tcp_receive, tcp_send

from socket import error as soc_err
from socket import timeout
from sessions import sesProcess
from Queue import Queue
import threading
import multiprocessing
import time
from server_common import read_games_from_file
# Constants -------------------------------------------------------------------
___NAME = 'Sudoku Protocol'
___VER = '0.1.0.0'
___DESC = 'Sudoku Protocol Server-Side'
___BUILT = '2017-11-02'
___VENDOR = 'Copyright (c) 2017'
# Static functions ------------------------------------------------------------
def __disconnect_client(sock):
	'''Disconnect the client, close the corresponding TCP socket
	@param sock: TCP socket to close (client socket)
	'''
	# Check if the socket is closed disconnected already ( in case there can
	# be no I/O descriptor
	try:
		sock.fileno()
	except soc_err:
		LOG.debug('Socket closed already ...')
		return
	# Closing RX/TX pipes
	LOG.debug('Closing client socket')
	# Close socket, remove I/O descriptor
	sock.close()
	LOG.info('Disconnected client')

def process_uname(sock, source, unman, activenames):
	#get username, check for duplicates
	m = tcp_receive(sock)
	LOG.info('New user from %s:%d picking username' % source)
	if m.startswith(REQ_UNAME):
		m=m.split(MSG_FIELD_SEP)[1]
		while m in activenames:
			try:
				tcp_send(client_socket, RSP_UNAME_TAKEN)
				m=tcp_teceive(client_socket)
				m=m.split(MSG_FIELD_SEP)[1]
			except (soc_error):
				LOG.info('Client failed to pick username from %s:%d' % source)
				__disconnect_client(client_socket)
				return
		LOG.info('Client %s:%d picked username %s' % source, m)
		unmanaged.put((m,client_socket,source))
		tcp_send(client_socket,RSP_OK)
	else:
		LOG.debug('Unknown control message received: %s ' % m)
		tcp_send(client_socket, RSP_UNKNCONTROL)

def serThread1(unman, sesss):
	'''
	Checks if there are unmanaged users to handle with new threads, checks if there are dead game sessions to remove from game session list (as the thread that creates the process dies after creating it).
	@param unman: Queue of (client_name,client_socket, source) tuples containing information about unmanaged clients. If there are any, pops and sends to a new thread to be managed.
	@param sesss: list of all active game sessions. Deletions managed by serThread1, additions by serThread2, list in Python is thread safe.
	'''
	#TODO: I defined fn and change as needed
	fn = 'application/server/sudoku_db'
	boards=read_games_from_file(fn)
	while True: #Serve forever :)
		try:
			#Clean game sessions in sesss
			toDie=[]
			for sess in sesss:
				if not sesss[sess].isAlive():
					toDie.append(sess)
			for s in toDie:
				del sesss[sess]
			#Send unmanaged users to be managed
			if not unman.empty():
				guest=unman.get()
				threading.Thread(target=serThread2, args=(guest,sesss, unman,boards)).start() #No running tally about connected guests
			time.sleep(1)
		except KeyboardInterrupt:
			LOG.info("Ctrl+C issued, exiting")
			for sess in sesss:
				sess.join() #make sure everything is deeeeaad!
			return #diiiie
def serThread2(guest, sesss, unman, boards):
	'''
	Manages each user that has connected to server but is not connected to a game session. User can check game session list, join a game session or start a new one.
	@param guest: (client_name,client_socket, source) tuple containing information about client
	@param sesss: list of all active game sessions. Deletions managed by serThread1, additions by serThread2, list in Python is thread safe.
	'''
	LOG.info('Managing user %s from %s:%d' % guest[0], guest[2])
	while True:
		guest[1].settimeout(1200) #clients should choose a game session in 20 minutes
		try:
			m = tcp_receive(guest[1])
			LOG.info('Received from sessionless user %s' % guest[0])
			if m.startswith(REQ_GET_SESS):
				ress=list(sesss.keys()) #list of session names
				res=MSG_FIELD_SEP.join([RSP_OK]+ress)
				tcp_send(guest[1],res)
			elif m.startswith(REQ_JOIN_SESS):
				message=m.split(MSG_FIELD_SEP)[1]
				if message not in sesss: #if game session no longer available, must have ended
					tcp_send(guest[1],RSP_SESSION_ENDED)
				else:
					guest[1].settimeout(None) #remove timeout
					sesss[message][1].put(guest) #guest sent to be managed by session, this thread has fulfilled its purpose
					return
			elif m.startswith(REQ_NEW_SESS):
				message=m.split(MSG_FIELD_SEP)[1].split(MSG_SEP)[0]
				prefpl =m.split(MSG_SEP)[1]
				if message in sesss: #session with this name already exists
					tcp_send(guest[1],RSP_SESSION_TAKEN)
				else: #creates new process for new session
					sesss[message]=(multiprocessing.Process(target=sesProcess, args=(message, multiprocessing.Queue(), unman, boards, prefpl)))
					guest[1].settimeout(None) #remove timeout
					sesss[message][1].put(guest) #guest sent to be managed by session
					return
			else:
				LOG.debug('Unknown control message received: %s ' % m)
				tcp_send(guest[1], RSP_UNKNCONTROL)
		except timeout:
			LOG.info('Client %s from %s:%d has timed out, disconnecting.' % client[0],client[2])
			tcp_send(guest[1], PUSH_TIMEOUT)
			__disconnect_client(guest[1])
			return #diiiie
		except soc_error:
			LOG.info('Problem with connection, dropping user from %s:%d' % client[2])
			client[1].close()
			return #diiiie
