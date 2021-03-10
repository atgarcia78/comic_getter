import argparse
import logging
from rco_downloader import (
    RCO_Downloader as RCO_DL,    
)
from concurrent.futures import ThreadPoolExecutor
import sys

from utils import (
    init_logging,
    init_argparse    
)  

from concurrent.futures import(
    ThreadPoolExecutor,
    wait,
    ALL_COMPLETED,
)

import aiorun
import asyncio
import uvloop

from queue import Queue
from codetiming import Timer

from threading import Thread
    

@Timer(name="decorator")
def main():
    
    parser = init_argparse()
    init_logging()
    logger = logging.getLogger("main")
    args = parser.parse_args()


    if args.pdf:
        data = args.input.split(",")
        RCO_DL.makepdfandclean((data[0], data[1]), 0, logger )
        sys.exit()

    if args.check:
        data = args.input.split(",")
        RCO_DL.sanitise(data[0], data[1])
        sys.exit()

    if args.checkall:
        list_data = args.checkall.split(",")
        logger.info(list_data)
        with ThreadPoolExecutor(thread_name_prefix="checkall", max_workers=6) as executor:
                futures = [executor.submit(RCO_DL.check_all(data_n)) for data_n in list_data] 
                wait(futures, return_when=ALL_COMPLETED)
        sys.exit()


    if not args.input:
        sys.exit("URL missing")

    else:

        try:
        
            main_url = args.input
            
            rco_dl = RCO_DL()          

            issues_links = rco_dl.get_issues_links(main_url, args.cache)
            
            #logger.info(issues_links)
            
            if not issues_links: sys.exit("No se han encontrado ejemplares del cómic")
            
            skip = args.skip
            if (skip != 0):
                issues_links = issues_links[skip:]

            #subset of consecutive issues
            first = args.first
            last = args.last
            if ((first != 0) and (last != 0)):
                issues_links = issues_links[first-1:last]


            #single issue
            if args.issue:
                issues_links = issues_links[args.issue-1:args.issue]


            n_workers = args.threads

            if args.verbose:
                logger.info(f"Number of comics: [{len(issues_links)}]")
                logger.info(f"Number of workers: [{n_workers}]")
                #logger.info(issues_links)
   
            if issues_links:
            
                try:

                    aiorun.run(rco_dl.run(issues_links), use_uvloop=True)                 

                except Exception as e:
                    logger.warning(f"Fail in pdf and postprocessing  {str(e)}")            

        except Exception as e:
            logger.warning(str(e), exc_info=True)
                  

if __name__ == "__main__":    
    
    main()