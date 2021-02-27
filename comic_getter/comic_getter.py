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

from pathlib import Path
from concurrent.futures import(
    ThreadPoolExecutor,
    ProcessPoolExecutor,
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
            
            issues_links = rco_dl.get_issues_links(main_url)
            
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

            
            n_issues = len(issues_links)

            n_workers = args.threads

            if args.verbose:
                logger.info("Number of comics: [{}]".format(n_issues))
                logger.info("Number of workers: [{}]".format(n_workers))
                logger.info(issues_links)
   
            rco_dl.put_issues_queue(issues_links)
            
            n_workers = rco_dl._NUM_DRIVERS
            
            if not rco_dl.ctx_dl['issues_queue'].empty():
            
                                            
        
                # with ThreadPoolExecutor(thread_name_prefix="comic", max_workers=n_workers + 1) as ex:
                
                #     futures_prod = [ex.submit(rco_dl.worker_prod, i) for i in range(n_workers)]
                #     #futures_prod = [ex.submit(rco_dl.worker_prod, 0)]
                #     fut = ex.submit(aiorun.run(rco_dl.async_dl(), use_uvloop=True))
                
                #     done, pending = wait([fut] + futures_prod, return_when=ALL_COMPLETED)
                #     #done, pending = wait(futures_prod, return_when=ALL_COMPLETED)                 
               
                #     if pending:
                #         try:
                #             ex.shutdown(wait=False, cancel_futures=True)
                #         except Exception as e:
                #             pass
                        
                                        
                #     if done:
                #         for d in done:
                #             try:                        
                #                 if d: 
                #                  exc = d.exception()
                #                  logger.debug(str(exc))
                                  
                #             except Exception as e:
                #                 logger.debug(str(e), exc_info=True)
            
                try:
                    
                    aiorun.run(rco_dl.run(), use_uvloop=True)
                    
                    rco_dl.close_nt_resources()
                    comics_to_pdf = rco_dl.check_dl_ok()
                    
                    logger.info(f"[COMIC2PDF] : {len(comics_to_pdf)}")
                    logger.info(comics_to_pdf)
           
                    ex = ThreadPoolExecutor(max_workers=20) 
                    futures = [ex.submit(rco_dl.makepdfandclean, comic) for comic in comics_to_pdf]
                    dones, _= wait(futures, return_when=ALL_COMPLETED)
                    for d in dones: logger.debug(str(d.exception()))
                    
                    
                    
                except Exception as e:
                    logger.warning(f"Fail in pdf and postprocessing  {str(e)}")            
                
                    
            
        except Exception as e:
            logger.warning(str(e), exc_info=True)
                  

if __name__ == "__main__":
    
    
    main()