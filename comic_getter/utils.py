import threading
import logging

def print_thr(msg):
    n = threading.currentThread().getName()
    #print(f"[{n}]: {msg}") 
    logging.info(f"[{n}]: {msg}")

def print_thr_error(msg):
    n = threading.currentThread().getName()
    #print(f"[{n}]: {msg}") 
    logging.error(f"[{n}]: {msg}")