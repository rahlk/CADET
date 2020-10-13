"""    -------    -------    -------    -------    -------    -------    -------    -------    -------    -------------
RUNSERVICE
Author: Shahriar Iqbal
Version: 0.1
    -------    -------    -------    -------    -------    -------    -------    -------    -------    -------    --------
"""
import sys
import os
import socket 
from datetime import datetime

from cadet.Configuration import Config as cfg
from cadet.set_workload import SetWorkload

def process_input():
    """This function is used to process input passed by user to select experiment.
    Returns
    -------
        options: options dictionary
    """
    options={}
    options['software_system']=sys.argv[1]
    # Deep Neural Network Systems1
    if options['software_system']=='Image':
       options['properties']={}
           
    return options
                             
if __name__=='__main__':
    options=process_input()
    if options['software_system']=='Image':
            SWL=SetWorkload(options)
            
    
   
              
