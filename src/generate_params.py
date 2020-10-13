import os 
import sys
import json
import random
import subprocess
import itertools 
import numpy as np
import pandas as pd

from cadet.perf import Perf
from cadet.config_params import ConfigParams 
from cadet.Configuration import Config as cfg
from cadet.compute_performance import ComputePerformance

random.seed(288)

class GenerateParams(object):
    """This class is used to generate parameters for running inference
    """
    def __init__(self,  software):
        print("[STATUS]: Initializing GenerateParams Class")
        self.perf_obj = Perf()       
       
        # constants
        self.ENABLE = "1"
        self.DISABLE = "0"
        self.NUM_TEST = 2
                
        # determine current system
        self.sys_name = self.get_sys_name()
        self.software = software
        self.output_file = os.path.join(os.getcwd(), cfg.output_dir)
        self.file_name_output = self.output_file + str(software) + ".csv"
        print (self.file_name_output)
        # columns of dataframe
        self.columns =  cfg.hardware_columns[self.sys_name]
        self.columns.extend (cfg.software_columns[self.software])
        self.columns.extend (cfg.measurement_columns)
        # run     
        self.initialize()
        self.run_experiment() 
                
    def initialize(self):
        # get list of big cores 
        self.big_cores = cfg.systems[self.sys_name]["cpu"]["cores"]
        try:
            if self.sys_name == "TX1":
                from cadet.TX1.Params import params
                self.params = params
            elif self.sys_name == "TX2":       
                from cadet.TX2.Params import configs
                self.params = configs      
            else:              
                return
              
        except:
            # get big core frequencies 
            self.big_core_freqs = self.get_big_core_freqs()
            self.big_core_freqs = filter(None, self.big_core_freqs)
        
            # get gpu frequencies
            self.gpu_freqs = self.get_gpu_freqs()
            self.gpu_freqs = self.freq_conversion(self.gpu_freqs)
        
            # get emmc frequencies
            self.emc_freqs = self.get_emc_freqs()
            self.emc_freqs = self.freq_conversion(self.emc_freqs)
        
            # generate all possible combinations 
            self.generate_params_combination()
            self.save_sampled_params()
               
    def run_experiment(self):
        """This function is used to run experiments"""
        # set config   
        for conf in range(0, len(self.params)):                             
            cur_conf = self.params[conf]
            cur_conf_name = "{0}{1}".format("Config",conf)        
            ConfigParams(cur_conf, self.sys_name, self.big_cores, 
                         self.columns)
            for iteration in range(self.NUM_TEST):
                    os.system('perf stat -e cycles,instructions,context-switches,cache-references,cache-misses,L1-dcache-loads,L1-dcache-load-misses,L1-dcache-stores,migrations,minor-faults,major-faults,branch-loads,branch-load-misses,emulation-faults,alignment-faults,branch-misses,raw_syscalls:sys_enter,raw_syscalls:sys_exit,block:*,sched:*,irq:*,ext4:* -o cur python3 /home/nvidia/CAUPER/cadet/ComputePerformance.py')
                    perf_output = self.perf_obj.parse_perf()    
                    with open ('measurement','r') as f:
                        data = json.load(f)
                    cur = list(cur_conf[:])
                    cur.append(data['cur_inference'])
                    cur.append(data['cur_total_power'])
                    cur.append(data['cur_gpu_power'])
                    cur.append(data['cur_cpu_power'])
                    cur.append(data['cur_total_temp'])
                    cur.append(data['cur_gpu_temp'])
                    cur.append(data['cur_cpu_temp'])
                    self.df = pd.DataFrame(np.array(cur).reshape(1, len(self.columns)))
                    self.df.columns = self.columns[:]
                    self.df = self.df.join(perf_output)
                    if not os.path.isfile(self.file_name_output):
                        self.df.to_csv(self.file_name_output)
                    else:
                        self.df.to_csv(self.file_name_output, header = False, mode="a")
            
                                                                                  
    def random_config_select(self):
        """This function is to select 1600 configurations randomly"""
        from random import randint
        from operator import itemgetter
        index = [randint(0, len(self.params)) for p in range(0, 1600)]
        return itemgetter(*index)(self.params) 
                                 
    def get_sys_name(self):
        """This function is used to determine the system id"""
        sys_id = subprocess.getstatusoutput("cat {}".format(str(cfg.sys_id_file)))[1]
        sys_name = cfg.sys_id_dict[sys_id]
        return sys_name
    
    def freq_conversion(self,array):
        """This function is is used to convert frequency from KHz to Hz
        Returns
    ------- 
            array: array where each element is converted to Hz from KHz """
        if not array[-1].isdigit():
            array.pop()
            array = ["{0}{1}".format(i,"000") for i in array]
        return array

    def get_big_core_freqs(self):
        """This function is used to get available frequencies for all the big cores
        Returns
        -------
            freq: list of available frequencies for big cores"""
        try:
            filename = cfg.systems[self.sys_name]["cpu"]["frequency"]["available"]
            freq = subprocess.getstatusoutput("cat {0}".format(filename))[1]
            if freq:
                freq = freq.split(" ")
                return freq
        except AttributeError:
            print("[ERROR]: big core frequency file does not exist")

    def get_gpu_freqs(self):
        """This function is used to get available gpu frequencies
        Returns
        -------
            freq: list of available frequencies for gpus"""
        try:
            filename = cfg.systems[self.sys_name]["gpu"]["frequency"]["available"]
            freq = subprocess.getstatusoutput("cat {0}".format(filename))[1]
            if freq:
                freq = freq.split(" ")
                return freq
        except AttributeError:
            print("[ERROR]: gbus frequency file does not exist")

    def get_emc_freqs(self):
        """This function is used to get available emmc frequencies
        Returns
        -------
            freq: list of available frequencies for emmc controller"""
        try:
            filename = cfg.systems[self.sys_name]["emc"]["frequency"]["available"]
            freq = subprocess.getstatusoutput("cat {0}".format(filename))[1]
            if freq:
                freq = freq.split(" ")
                return freq
        except AttributeError:
            print("[ERROR]: emc frequency file does not exist")
    
    def get_software_config_options(self):
        """This function is used to generate software config options"""
        if self.software == "Image": 
            # memory growth, clear session
            software_var = [(-1, 0.5, 0.9)] 
        elif self.software == "NLP": 
            # memory growth, clear session
            software_var = [(-1, 0.5, 0.9)] 
        elif self.software == "Speech": 
            # memory growth, clear session
            software_var = [(-1, 0.5, 0.9)] 
        elif self.software == "x264": 
            # preset, bit rate, filter
            software_var =[(),(),()] 
        elif self.software == "SQLite": 
            # journal, synchronous, cache size, page size
            software_var = [(),(),()] 
        else: 
            print ("[ERROR]: software system not supported") 
            return
        software_var = list(itertools.product(*software_var)) 
        return software_var  
    
    def get_os_config_options(self):
        """This function is used to get os config options"""
         # OS configs 
        cache_pressure = (0, 100, 500)
        swappiness = (10, 60, 100)
        dirty_bg_ratio = (5, 50)
        dirty_ratio = (10, 80)
        drop_caches = (0, 3)
        sched_child_runs_first = (0, 1)
        sched_rt_runtime = (500000, 950000)
        policy = (0, 1)
        var = [cache_pressure, swappiness, dirty_bg_ratio,
               dirty_ratio, drop_caches, sched_child_runs_first, 
               sched_rt_runtime, policy]
        os_var = list(itertools.product(*var))
        return os_var 
    
    def get_hardware_config_options(self):
        """This function is used to get hardware configuration options"""
        # cpu frequency
        core_freq = self.big_core_freqs
        # gpu frequency 
        gpu_freq = self.gpu_freqs[:]    
        # memory controller frequency       
        emc_freq = self.emc_freqs[:]          
        # create configurable paramters set before permutation in a varibale named var
        status_var = [(self.ENABLE, self.DISABLE, self.DISABLE, self.DISABLE),
                     (self.ENABLE, self.DISABLE, self.DISABLE, self.ENABLE),
                     (self.ENABLE, self.DISABLE, self.ENABLE, self.DISABLE),
                     (self.ENABLE, self.DISABLE, self.ENABLE, self.ENABLE),
                     (self.ENABLE, self.ENABLE, self.DISABLE, self.DISABLE),
                     (self.ENABLE, self.ENABLE, self.DISABLE, self.ENABLE),
                     (self.ENABLE, self.ENABLE, self.ENABLE, self.DISABLE),
                     (self.ENABLE, self.ENABLE, self.ENABLE, self.ENABLE)]
        var = [core_freq, gpu_freq, emc_freq]
        hw_var = list(itertools.product(*var))
        hw_var = list(itertools.product(status_var, hw_var))      
        for i in range(len(hw_var)):
            hw_var[i] = hw_var[i][0] + hw_var[i][1]
        hw_var = list(hw_var for hw_var,_ in itertools.groupby(hw_var))
        return hw_var 
    
    def generate_params_combination(self):
        """This function is used to generate parameter combination using hardware, 
        os and software system configuration options"""
        # hardware configs
        hw_var = self.get_hardware_config_options()
        # os configs
        os_var = self.get_os_config_options()
        # software configs
        soft_var = self.get_software_config_options()
        # os-software-configs
        os_soft_var = list(itertools.product(os_var, soft_var)) 
            
        for i in range(len(os_soft_var)):
            os_soft_var[i] = os_soft_var[i][0] + os_soft_var[i][1]
        os_soft_var = list(os_soft_var for os_soft_var,_ in itertools.groupby(os_soft_var))
        # select 1600 samples
        hw_sampled_var = random.sample(hw_var, 1600)
        os_soft_sampled_var = random.sample(os_soft_var, 1600)
        # sampled_params
        self.params = []
        for i in range(1600):
            self.params.append(hw_sampled_var[i] + os_soft_var[i])
                
    def save_sampled_params(self):
        """This function is used to extract the valid params from all the combination of params"""       
        # save to a file for temporary use     
        params_file = os.path.join(self.sys_name, cfg.config_file)
        filename = os.path.join(os.getcwd(), params_file)
        with open(filename, "w") as f:
            f.write('params = %s' %self.params)
       
