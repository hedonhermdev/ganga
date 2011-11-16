#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#
'''Parent for all Gaudi and GaudiPython applications in LHCb.'''

import os
import tempfile
import gzip
import shutil
from Ganga.GPIDev.Schema import *
from Ganga.GPIDev.Adapters.IApplication import IApplication
from Ganga.GPIDev.Adapters.IPrepareApp import IPrepareApp
import CMTscript
from GangaLHCb.Lib.Gaudi.CMTscript import parse_master_package
import Ganga.Utility.logging
from Ganga.Utility.files import expandfilename, fullpath
from GangaLHCb.Lib.LHCbDataset.LHCbDataset import LHCbDataset
from GangaLHCb.Lib.LHCbDataset.OutputData import OutputData
from GaudiUtils import *
from Ganga.GPIDev.Lib.File import File
from Ganga.Core import ApplicationConfigurationError
import Ganga.Utility.Config
#from GaudiAppConfig import *
from Ganga.Utility.files import expandfilename

logger = Ganga.Utility.logging.getLogger()

#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#

def get_common_gaudi_schema():
    schema = {}
    docstr = 'The version of the application (like "v19r2")'
    schema['version'] = SimpleItem(preparable=1,defvalue=None,
                                   typelist=['str','type(None)'],doc=docstr)
    docstr = 'The platform the application is configured for (e.g. ' \
             '"slc4_ia32_gcc34")'
    schema['platform'] = SimpleItem(preparable=1,defvalue=None,
                                    typelist=['str','type(None)'],doc=docstr)
    docstr = 'The package the application belongs to (e.g. "Sim", "Phys")'
    schema['package'] = SimpleItem(preparable=1,defvalue=None,
                                   typelist=['str','type(None)'],doc=docstr)
    docstr = 'The user path to be used. After assigning this'  \
             ' you can do j.application.getpack(\'Phys DaVinci v19r2\') to'  \
             ' check out into the new location. This variable is used to '  \
             'identify private user DLLs by parsing the output of "cmt '  \
             'show projects".'
    schema['user_release_area'] = SimpleItem(preparable=1,defvalue=None,
                                             typelist=['str','type(None)'],
                                             doc=docstr)
    docstr = 'The package where your top level requirements file is read '  \
             'from. Can be written either as a path '  \
             '\"Tutorial/Analysis/v6r0\" or in a CMT style notation '  \
             '\"Analysis v6r0 Tutorial\"'
    schema['masterpackage'] = SimpleItem(preparable=1,defvalue=None,
                                         typelist=['str','type(None)'],
                                         doc=docstr)
    docstr = 'Extra options to be passed onto the SetupProject command '  \
             'used for configuring the environment. As an example '  \
             'setting it to \'--dev\' will give access to the DEV area. '  \
             'For full documentation of the available options see '  \
             'https://twiki.cern.ch/twiki/bin/view/LHCb/SetupProject'
    schema['setupProjectOptions'] = SimpleItem(preparable=1,defvalue='',
                                               typelist=['str','type(None)'],
                                               doc=docstr)
    return schema

#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#

class Francesc(IPrepareApp):
    '''Parent for all Gaudi and GaudiPython applications, should not be used
    directly.'''    
    _name = 'Francesc'
    _exportmethods = ['getenv','getpack', 'make', 'cmt']
    _schema = Schema(Version(1, 1), {})

    def get_gaudi_appname(self):
        '''Handles the (unfortunate legacy) difference between Gaudi and
        GaudiPython schemas wrt this attribute name.'''
        appname = ''
        try: appname = self.appname
        except AttributeError:
            appname = self.project
        return appname

    def _init(self,gaudi_app,set_ura):
        self.extra = GaudiExtras()
        if (not self.version): self.version = guess_version(gaudi_app)
        if (not self.platform): self.platform = get_user_platform()
        if (not self.package): self.package = available_packs(gaudi_app)
        if not set_ura: return
        if not self.user_release_area:
            expanded = os.path.expandvars("$User_release_area")
            if expanded == "$User_release_area": self.user_release_area = ""
            else:
                self.user_release_area = expanded.split(os.pathsep)[0]
        #self.appconfig = GaudiAppConfig()

    def _check_gaudi_inputs(self,optsfiles,appname):
        """Checks the validity of some of user's entries."""
        for fileitem in optsfiles:
            fileitem.name = os.path.expanduser(fileitem.name)
            fileitem.name = os.path.expandvars(fileitem.name)
            fileitem.name = os.path.normpath(fileitem.name)
    
        if appname is None:
            msg = "The appname is not set. Cannot configure."
            logger.error(msg)
            raise ApplicationConfigurationError(None,msg)
    
        if appname not in available_apps():
            if appname is 'Bender': return
            msg = "Unknown application %s. Cannot configure." % appname
            logger.error(msg)
            raise ApplicationConfigurationError(None,msg)
    
    def _getshell(self):
        appname = self.get_gaudi_appname()
        ver  = self.version
        opts = ''
        if self.setupProjectOptions: opts = self.setupProjectOptions

        fd = tempfile.NamedTemporaryFile()
        script = '#!/bin/sh\n'
        if self.user_release_area:
            script += 'User_release_area=%s; export User_release_area\n' % \
                      expandfilename(self.user_release_area)
        if self.platform:    
            script += 'export CMTCONFIG=%s\n' % self.platform
        useflag = ''
        if self.masterpackage:
            (mpack, malg, mver) = parse_master_package(self.masterpackage)
            useflag = '--use \"%s %s %s\"' % (malg, mver, mpack)
        cmd = '. SetupProject.sh %s %s %s %s' % (useflag,opts,appname,ver) 
        script += '%s \n' % cmd
        fd.write(script)
        fd.flush()
        logger.debug(script)

        self.shell = Shell(setup=fd.name)
        logger.debug(pprint.pformat(self.shell.env))
        
        fd.close()
        app_ok = False
        ver_ok = False
        for var in self.shell.env:
            if var.find(self.get_gaudi_appname()) >= 0: app_ok = True
            if self.shell.env[var].find(self.version) >= 0: ver_ok = True
        if not app_ok or not ver_ok:
            msg = 'Command "%s" failed to properly setup environment.' % cmd
            logger.error(msg)
            raise ApplicationConfigurationError(None,msg)

    def getenv(self):
        '''Returns a copy of the environment used to flatten the options, e.g.
        env = DaVinci().getenv(), then calls like env[\'DAVINCIROOT\'] return
        the values.
        
        Note: Editing this does not affect the options processing.
        '''
        try:
            job = self.getJobObject()
        except:
            self._getshell()
            return self.shell.env.copy()
        env_file_name = job.getInputWorkspace().getPath() + '/gaudi-env.py.gz'
        if not os.path.exists(env_file_name):
            self._getshell()
            return self.shell.env.copy()
        else:
            in_file = gzip.GzipFile(env_file_name,'rb')
            exec(in_file.read())
            in_file.close()
            return gaudi_env
    
    def getpack(self, options=''):
        """Execute a getpack command. If as an example dv is an object of
        type DaVinci, the following will check the Analysis package out in
        the cmt area pointed to by the dv object.

        dv.getpack('Tutorial/Analysis v6r2')
        """
        # Make sure cmt user area is there
        cmtpath = expandfilename(self.user_release_area)
        if cmtpath:
            if not os.path.exists(cmtpath):
                try:
                    os.makedirs(cmtpath)
                except Exception, e:
                    logger.error("Can not create cmt user directory: "+cmtpath)
                    return
                
        command = 'getpack ' + options + '\n'
        CMTscript.CMTscript(self,command)

    def make(self, argument=''):
        """Build the code in the release area the application object points
        to. The actual command executed is "cmt broadcast make <argument>"
        after the proper configuration has taken place."""
        #command = '###CMT### broadcast -global -select=%s cmt make ' \
        #          % self.user_release_area + argument
        config = Ganga.Utility.Config.getConfig('LHCb')
        command = config['make_cmd']
        CMTscript.CMTscript(self,command)

    def cmt(self, command):
        """Execute a cmt command in the cmt user area pointed to by the
        application. Will execute the command "cmt <command>" after the
        proper configuration. Do not include the word "cmt" yourself."""
        command = '###CMT### ' + command
        CMTscript.CMTscript(self,command)

    def _prepare(self,input_dir):
        #self.extra = GaudiExtras()
        self._getshell()
        send_to_share=[]

        if not self.user_release_area: return

        appname = self.get_gaudi_appname()
        dlls, pys, subpys = get_user_dlls(appname, self.version,
                                          self.user_release_area,self.platform,
                                          self.shell)
        #self.appconfig.inputsandbox += [File(f,subdir='lib') for f in dlls]
        for f in dlls:
            if not os.path.isdir(os.path.join(input_dir,'lib')): os.makedirs(os.path.join(input_dir,'lib')) 
            share_path = os.path.join(input_dir,'lib',f.split('/')[-1])
            shutil.copy(expandfilename(f),share_path)
            send_to_share.append(File(share_path,subdir='lib'))
        for f in pys:
            tmp = f.split('InstallArea')[-1]
            subdir = 'InstallArea' + tmp[:tmp.rfind('/')+1]
            if not os.path.isdir(os.path.join(input_dir,subdir)): os.makedirs(os.path.join(input_dir,subdir))
            share_path = os.path.join(input_dir,subdir,f.split('/')[-1])
            shutil.copy(expandfilename(f),share_path)
            #File(f).create(share_path)
            #share_file = File(name=share_path,subdir=subdir)
            #share_file.subdir = subdir
            #send_to_share.append(share_file)
            send_to_share.append(File(name=share_path,subdir=subdir))
        for dir, files in subpys.iteritems():
            for f in files:
                tmp = f.split('InstallArea')[-1]
                subdir = 'InstallArea' + tmp[:tmp.rfind('/')+1]
                if not os.path.isdir(os.path.join(input_dir,subdir)): os.makedirs(os.path.join(input_dir,subdir))
                share_path = os.path.join(input_dir,subdir,f.split('/')[-1])
                shutil.copy(expandfilename(f),share_path)
                #File(f).create(share_path)
                #share_file = File(name=share_path,subdir=subdir)
                #share_file.subdir = subdir
                #send_to_share.append(share_file)
                send_to_share.append(File(name=share_path,subdir=subdir))

        return send_to_share

    def _master_configure(self):
        '''Handles all common master_configure actions.'''
        pass
        ## job=self.getJobObject()                
##         if job.inputdata: self.appconfig.inputdata = job.inputdata
##         if job.outputdata: self.appconfig.outputdata = job.outputdata

    def _configure(self):
        pass
        # return self.appconfig.inputdata.optionsString()




    #def postprocess(self):
        #from Ganga.GPIDev.Adapters.IApplication import PostprocessStatusUpdate
        #job = self.getJobObject()
        #if job:
        #raise PostprocessStatusUpdate("failed")
        
#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#

class GaudiExtras:
    '''Used to pass extra info from Gaudi apps to the RT-handler.'''
    _name = "GaudiExtras"
    _category = "extras"

    def __init__(self):
        self.master_input_buffers = {}
        self.master_input_files = []
        self.input_buffers = {}
        self.input_files = []
        self.inputdata = LHCbDataset()
        self.outputsandbox = []
        self.outputdata = OutputData()
        self.input_buffers['data.py'] = ''

#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#
