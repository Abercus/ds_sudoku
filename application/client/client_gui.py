# Setup Python logging --------------------------------------------------------
import logging
FORMAT='%(asctime)s (%(threadName)-2s) %(message)s'
logging.basicConfig(level=logging.INFO,format=FORMAT)
LOG = logging.getLogger()

# Imports----------------------------------------------------------------------
from application.common import TCP_RECEIVE_BUFFER_SIZE, \
    RSP_OK, RSP_UNKNCONTROL, \
    REQ_UNAME, REQ_GET_SESS, REQ_JOIN_SESS, REQ_NEW_SESS, \
    MSG_FIELD_SEP, MSG_SEP, RSP_UNAME_TAKEN,RSP_OK_GET_SESS, RSP_SESSION_ENDED, RSP_SESSION_TAKEN,\
    PUSH_END_SESSION, PUSH_UPDATE_SESS

import tkFont as tkfont
import tkMessageBox as tm
from Queue import Queue
from Tkinter import *
from threading import Thread
from time import sleep

from application.client.gameboard import GameBoard
from gui_parts import LoginFrame, ConnectFrame, SessionsFrame
from ast import literal_eval



class Application(Tk):
    '''
    Launch the main part of the GUI
    '''
    def __init__(self, client, *args, **kwargs):
        Tk.__init__(self, *args, **kwargs)
        self.title('Sudoku Game')
        self.geometry('490x350')
        self.title_font = tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")
        # Assign client object
        self.client = client
        # Create Queue. This queue will be used by server listening thread and update_gui thread
        self.queue = Queue()
        # Array to store the threads
        self.threads = []

        # Main container to store parts of the gui
        container = Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Array of frames to store parts of the gui
        self.frames = {}
        self.fnames = (LoginFrame, ConnectFrame, SessionsFrame, GameBoard)
        for F in self.fnames:
            page_name = F.__name__
            frame = F(master=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Show LoginFrame first
        self.show_frame("LoginFrame")

    def show_frame(self, page_name):
        '''
        Show frame by name
        @param page_name: name of the frame to show
        '''
        self.frame = self.frames[page_name]
        self.fname = page_name
        self.frame.tkraise()

    def connect_server(self, srv_addr = ''):
        '''
        Connect to the server
        @param srv_addr: server address
        '''

        # Default server address is 127.0.0.1:7777
        if srv_addr == '':
            srv_addr = '127.0.0.1'+':'+'7777'

        a, b = srv_addr.split(':')
        if self.client.connect((a,int(b))):
            # If successfully connected to the server create threads

            # Gui thread to update gui when response is received from the server
            gui = Thread(name='GuiProcessor', \
                         target=self.update_gui, args=(self.queue,))
            self.threads.append(gui)

            # Server thread to listen the responses from the server
            ser = Thread(name='ServerProcessor', \
                       target=self.client.loop, args=(self.queue,))
            self.threads.append(ser)

            # Start threads
            for t in self.threads:
                t.start()

            tm.showinfo("Login info", "Connected to the server")
            return TRUE
        return FALSE


    def send_username(self, username):
        '''
        Send entered username to the server
        @param username: user name
        '''
        return self.client.send_username(username)

    def send_guess(self, x, y, value):
        '''
        Send entered number to the server to check if it is right ot not
        @param x: x coordinate on the board
        @param y: y coordinate on the board
        @param value: entered number
        '''
        msg = str(x) + str(y) + str(value)
        return self.client.send_guess(msg)

    def get_sess(self):
        '''
        Send request to the server to get current sessions list
        '''
        return self.client.get_sess()

    def join_sess(self, sess_id):
        '''
        Send request to the server to join a session
        @param sess_id: name of the session to join
        '''
        self.client.join_sess(msg=sess_id)

    def create_sess(self, num_of_players, sess_name):
        '''
        Send request to the server to create new session
        @param num_of_players: desired number of players entered
        @param sess_name: name of the session entered
        '''
        msg = num_of_players + MSG_SEP + sess_name
        self.client.create_sess(msg=msg)

    def exit_game(self):
        '''
        Send request to the server to leave the session
        '''
        self.client.exit_game()


    def update_gui(self, q):
        '''
        Gui thread logic: updates gui according to the response that server returns
        @param q: queue of the responses from the server
        '''
        logging.info('GuiProcessor started ....' )

        while 1:
            if not q.empty():
                # Get next message from queue to work on
                message = q.get()
                logging.info('Received [%d bytes] in total' % len(message))
                logging.info("Received message: %s" % message)
                # If message is too short
                if len(message) < 2:
                    logging.debug('Not enough data received from %s ' % message)
                    return
                logging.debug('Response control code (%s)' % message[0])

                # When server responds RSP_OK then everything was OK.
                if message.startswith(RSP_OK + MSG_FIELD_SEP):
                    # We find for which frame this ok was for (where client currently is):
                    currentFrame = str(self.fname).split(".")[-1]
                    # If we are in sessions list.
                    if currentFrame == "SessionsFrame":
                        if MSG_SEP not in message and len(message) > 2:
                            # We got back a list of sessions! Lets add them to our list.
                            logging.debug('Sessions retrieved ...')
                            msgs = literal_eval(message[2:])
                            self.frame.sessions.delete('1.0', END)
                            for m in msgs:
                                self.frame.sessions.insert(END, m + "\n")
                            continue
                    # If we are in game
                    if currentFrame == "GameBoard":
                        # If already in gameboard. Joined before.
                        # If board is returned
                        if message.startswith(RSP_OK + MSG_FIELD_SEP + "[["):
                            b = message[message.find(MSG_FIELD_SEP) + 1:]
                            board, players = b.split(MSG_SEP)
                            # got board and players. Update players list ands core board
                            self.frame.clearBoard()
                            self.frame.initBoard(literal_eval(board))
                            self.frame.updatePlayers(literal_eval(players))
                            continue
                    # Look through frames we might be on
                    for i in range(len(self.fnames)):
                        if str(self.fnames[i]).split(".")[-1] == currentFrame:
                            # to get around connect-to-server screen if we have username problems
                            if str(self.fname).split(".")[-1] == "LoginFrame":
                                self.show_frame(str(self.fnames[i + 2]).split(".")[-1])
                                self.get_sess()
                            else:
                                self.show_frame(str(self.fnames[i + 1]).split(".")[-1])
                                # If going to sessions screen
                                if str(self.fnames[i + 1]).split(".")[-1] == "SessionsFrame":
                                    self.get_sess()
                                # If going to game screen
                                elif str(self.fnames[i + 1]).split(".")[-1] == "GameBoard":
                                    if message.startswith(RSP_OK + MSG_FIELD_SEP + "[["):
                                        # We got first game data from server
                                        b = message[message.find(MSG_FIELD_SEP)+1:]
                                        board, players = b.split(MSG_SEP)
                                        # got board and players. Update players list
                                        self.frame.clearBoard()
                                        self.frame.initBoard(literal_eval(board))
                                        self.frame.updatePlayers(literal_eval(players))
                                    else:
                                        # When game hasn't started.
                                        self.frame.clearBoard()
                                        self.frame.updatePlayers({})

                                        # going to game screen, we should have
                            break

                # When username was already used by someone, display error
                elif message.startswith(RSP_UNAME_TAKEN + MSG_FIELD_SEP):
                    tm.showerror("Login error", "This username is taken, try another one")
                    self.frames["LoginFrame"].rep=True
                    self.show_frame("LoginFrame")

                # When session user tries to join has already ended.
                elif message.startswith(RSP_SESSION_ENDED + MSG_FIELD_SEP):
                    tm.showerror("Login error", "Session ended choose another")

                # When session name is already in use.
                elif message.startswith(RSP_SESSION_TAKEN + MSG_FIELD_SEP):
                    tm.showerror("Login error", "This session name is taken, try another one")

                # When game session has updated from server side we do local updates as well
                elif message.startswith(PUSH_UPDATE_SESS + MSG_FIELD_SEP):
                    # If it was correct guess then we updat board
                    if message.startswith(PUSH_UPDATE_SESS+MSG_FIELD_SEP+"1"):
                        # Correct guess
                        board, ldb = message[3:].split(MSG_SEP)
                        self.frame.updatePlayers(literal_eval(ldb))
                        self.frame.initBoard(literal_eval(board))
                    else:
                        # Else we only update leaderboard
                        ldb = literal_eval(message.split(MSG_SEP)[1])
                        self.frame.updatePlayers(ldb)

                # When session ends - we got a winner.
                elif message.startswith(PUSH_END_SESSION + MSG_FIELD_SEP):
                    msgs = message.split(MSG_FIELD_SEP)[1]
                    if msgs == self.username:
                        tm.showinfo("Info", "Congratulations you win")
                    else: tm.showinfo("Info", "Winner is " + msgs)
                    self.show_frame("SessionsFrame")
                    self.get_sess()
                # In case of unknown responses.
                else:
                    logging.debug('Unknown control message received: %s ' % message)
                    return RSP_UNKNCONTROL

            else:
                sleep(0.1)
