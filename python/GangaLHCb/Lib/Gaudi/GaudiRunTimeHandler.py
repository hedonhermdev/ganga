#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#
from Ganga.GPIDev.Lib.Job import Job
from Ganga.GPIDev.Adapters.IRuntimeHandler import IRuntimeHandler
from Ganga.Utility.files import expandfilename
import Ganga.Utility.logging
from Ganga.GPIDev.Adapters.StandardJobConfig import StandardJobConfig
import Ganga.Utility.Config 
from RTHUtils import *
from GangaLHCb.Lib.LHCbDataset.LHCbDataset import *
from GangaLHCb.Lib.LHCbDataset.LHCbDatasetUtils import *
from GangaLHCb.Lib.Gaudi.GaudiJobConfig import GaudiJobConfig
from GangaLHCb.Lib.LHCbDataset.OutputData import OutputData
from Ganga.GPIDev.Base.Proxy import isType
from Ganga.GPIDev.Lib.File.FileBuffer import FileBuffer
from Ganga.Core import TypeMismatchError

logger = Ganga.Utility.logging.getLogger()
#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#

class GaudiRunTimeHandler(IRuntimeHandler):
    """This is the application runtime handler class for Gaudi applications 
    using the local, interactive and LSF backends."""
  
    def __init__(self):
        pass
  
    def master_prepare(self,app,appmasterconfig):
        ## Note only things sent to submit method in backend are EITHER the master
        ## inputsandbox OR the job.inputsandbox (see NOTE below as to which) as
        ## defined within the return of this function and the subjobconfig object
        ## returned from the prepare method below.
        job=app.getJobObject()

        outputsandbox=[]
        outdata=[]
        ## catch errors from not preparing properly
        if hasattr(app,'is_prepared') and app.is_prepared is not None:
            ## Pickup outputsandbox defined in the options file
            import pickle
            f_osandbox = os.path.join(app.is_prepared.name,'outputsandbox.pkl')
            if os.path.isfile(f_osandbox):
                file=open(f_osandbox,'rb')
                outputsandbox = pickle.load(file)
                file.close()
        ## Pickup outputdata defined in the options file
            f_odata = os.path.join(app.is_prepared.name,'outputdata.pkl')
            if os.path.isfile(f_odata):
                file=open(f_odata,'rb')
                outdata = pickle.load(file)
                file.close()
        else:
            logger.warning('Application is not prepared properly, ignoring outputsandbox and outputdata defined in options file(s)')
        
 #       self.appconfig.outputsandbox,outputdata = parser.get_output(job)
##         self.appconfig.outputdata.files += outputdata
##         self.appconfig.outputdata.files = unique(self.appconfig.outputdata.files)
        #self.appconfig = appmasterconfig

        ## Note EITHER the master inputsandbox OR the job.inputsandbox is added to
        ## the subjob inputsandbox depending if the jobmasterconfig object is present
        ## or not... Therefore combine the job.inputsandbox with appmasterconfig.
        inputsandbox=job.inputsandbox[:]
        if job.inputdata and job.inputdata.hasLFNs():
            xml_catalog_str = job.inputdata.getCatalog()
            inputsandbox.append(FileBuffer('catalog.xml'))
            
        ## Here add any sandbox files coming from the appmasterconfig
        ## currently none.
        inputsandbox += appmasterconfig.getSandboxFiles()


        ## Here return a GaudiJobConfig built on the StandardJobConfig but also
        ## containing outputdata attribute since we can define outputdata in
        ## optfiles
        return GaudiJobConfig(inputbox=inputsandbox, outputbox=outputsandbox, outputdata=outdata)

    def prepare(self,app,appsubconfig,appmasterconfig,jobmasterconfig):

        job = app.getJobObject()
        inputsandbox=[]
        ## Add the job.inputsandbox as splitters create subjobs that are
        ## seperate Job objects and therefore have their own job.inputsandbox
        ## which can be appended to in the splitters.
        inputsandbox = job.inputsandbox[:]

        ## Here add any sandbox files coming from the appsubconfig
        ## currently none.
        inputsandbox += appsubconfig.getSandboxFiles()

        ## Note the master inputsandbox will be added automatically
        ## no need to add it here
        data_str=''
        if job.inputdata:
            data_str = job.inputdata.optionsString()
            if job.inputdata.hasLFNs():
                cat_opts='\nfrom Gaudi.Configuration import FileCatalog\nFileCatalog().Catalogs = ["xmlcatalog_file:catalog.xml"]\n'
                data_str += cat_opts

        ## Unlike in the applications prepare method, buffers are created into
        ## files later on in job submission.
        ## Additional as data.py could be created in OptionsFileSplitter,
        ## Need to add the existing data.py content to the end of this, if present.
        # inputsandbox.append(FileBuffer('data.py',data_str).create())
        existing_data = [file for file in inputsandbox if file.name is 'data.py']
        if existing_data:
            if len(existing_data) is not 1:
                logger.warning('Appear to have more than one data.py file in inputsandbox, contact ganga developers!')
            if not isType(existing_data[0],FileBuffer):
                logger.error('Found data.py in inputsandbox but not of type \'FileBuffer\', contact ganga developers!')
                raise TypeMismatchError('Expected file data.py to be of type FileBuffer.')
            else:
                existing_data[0]._contents=data_str + existing_data[0].getContents()
        else:
            inputsandbox.append(FileBuffer('data.py',data_str))


        ## Strangly NEITHER the master outputsandbox OR job.outputsandbox
        ## are added automatically. As can define outputsandbox in optsfile
        ## will add it here
        outputsandbox=job.outputsandbox[:]
        outputsandbox += jobmasterconfig.getOutputSandboxFiles()
        outputsandbox += appsubconfig.getOutputSandboxFiles()


        ## As can define outputdata in the optsfiles need to pick this up from
        ## jobmasterconfig. Also append any job.outputdata for processing in
        ## create_runscript
        outputdata=OutputData()
        outputdata.files += jobmasterconfig.outputdata
        if job.outputdata:
            outputdata.files += job.outputdata


##         if appsubconfig.inputdata and appsubconfig.inputdata.hasLFNs():
##             s='\nFileCatalog().Catalogs = ["xmlcatalog_file:catalog.xml"]\n'
##             appsubconfig.input_buffers['data.py'] += s

        #sandbox = get_input_sandbox(appsubconfig)
        #outdata = appsubconfig.outputdata
        script = create_runscript(app,outputdata,job)

        return StandardJobConfig(FileBuffer('gaudiscript.py',script,
                                            executable=1),
                                 inputbox=inputsandbox,
                                 outputbox=outputsandbox)
        
#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#
