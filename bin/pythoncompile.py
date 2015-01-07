#!/usr/bin/python
import os
import subprocess
import sys, getopt
import time
import re
import datetime
import json
import copy
import hashlib
import shutil
from pprint import pprint
from subprocess import *


VERSION = 3.1

REGEXP_IMPORT = re.compile('/// *<reference path="(.*)/([^/]+)/[^"]+" */>')
#REGEXP_IMPORT_D_TS = re.compile('/// *<reference path=".*/([^/]+)/[^.]+\.class\.d\.ts" */>')
REGEXP_IMPORT_D_TS = re.compile('/// *<reference path="([^"]+)" */>')
REGEXP_IMPORT_D_TS_IMPORT = re.compile('/// *<reference path="(.*/[^/]+/[^.]+\.class\.d\.ts)" */>')
REGEXP_IMPORT_CUSTOM = re.compile('/// *< *([a-z]+)="([^"]+)" *([^/]+)? */>')
REGEXP_CUSTOM = re.compile('/// *< *([a-z]+) */>')

ESVersion = 3
USE_SOUND = True
USE_NOTIFICATION = True
TYPESCRIPT_PATH = None

class Console:
    def __init__(self):
        self.__colors = {'RED':'\033[91m', 'BLUE':'\033[94m', 'GREEN':'\033[92m', 'ORANGE':'\033[93m', 'NORMAL':'\033[0m'}

    def getColor(self, name):
        return self.__colors[name]

    def red(self, value):
        value = self.__treat(value)
        self.__print(self.__colors['RED'] + str(value) + self.__colors['NORMAL'])

    def green(self, value):
        value = self.__treat(value)
        self.__print(self.__colors['GREEN'] + str(value) + self.__colors['NORMAL'])

    def blue(self, value):
        value = self.__treat(value)
        self.__print(self.__colors['BLUE'] + str(value) + self.__colors['NORMAL'])

    def orange(self, value):
        value = self.__treat(value)
        self.__print(self.__colors['ORANGE'] + str(value) + self.__colors['NORMAL'])

    def normal(self, value):
        value = self.__treat(value)
        self.__print(self.__colors['NORMAL'] + str(value))


    def error(self, value):
        value = self.__treat(value)
        self.red("[ERROR]:"+str(value))

    def info(self, value):
        value = self.__treat(value)
        self.blue("[INFO]:"+str(value))

    def out(self, value):
            value = self.__treat(value)
            now = datetime.datetime.now()
            self.normal("[OUT "+now.strftime("%d-%m-%Y %H:%M:%S")+"]:"+str(value))
    def __treat(self, value):
        if((value is None)):
            value = "None"
        if(not value):
            value = "empty"
        try:
            value = str(value)
        except:
            print(value)
            value = ""
        return value

    def __print(self, value):
        print(value)


class MegaWatcher:
    def __init__(self, folders):
        self.__folders = folders
        self.__fileWatchers = {} 
        self.__compilations = 0
        self.__errors = 0

        start_time = time.time()
        #LOG.green(folders)
        
        for folder in self.__folders:
            name =  folder.split("/")[-1]
            self.__fileWatchers[name] = TSFilesWatcher(folder, self, name)

        try:
            file_config=open('.cache_metacompile.json','r')

            data = json.load(file_config)
            file_config.close()
            for key in data.keys():
                parentName = key.split("/")[0]
                module = key.split("/")[1]
                if(parentName in self.__fileWatchers):
                    if(self.__fileWatchers[parentName].hasModule(module)):
                        self.__fileWatchers[parentName].getModule(module).setDependencyMD5(data[key]["dependencies"])
                        self.__fileWatchers[parentName].getModule(module).setError(data[key]["errors"])
                        self.__fileWatchers[parentName].getModule(module).setLastDate(data[key]["last_date"])
                        #force recompilation of errors
                        if(data[key]["errors"]):
                            self.__fileWatchers[parentName].getModule(module).setLastCompilationDate(0)
                        else:
                            self.__fileWatchers[parentName].getModule(module).setLastCompilationDate(data[key]["last_date_compilation"])
                        self.__fileWatchers[parentName].getModule(module).init()
        except Exception as error:
            LOG.orange("No previous compilation found")
            print(error)
            pass
        

        keys = self.__fileWatchers.keys()
        #for name in keys:
            #LOG.red("compiling module "+name)
            #self.__fileWatchers[name].compileAll()


        for name in keys:
            #LOG.red("dependencies module "+name)
            self.__fileWatchers[name].checkDependenciesAll()


        self.compileAll()
        LOG.green("MetaTypescript Compiler v"+str(VERSION)+" is ready in "+str(round(time.time()-start_time,2))+"s")
        self.watch()

    def hasModule(self, moduleName, name = None):
        if(name is None):
            name = moduleName.split("/")[0]
            moduleName = moduleName.split("/")[1]

        if(name in self.__fileWatchers.keys()):
            return self.__fileWatchers[name].hasModule(moduleName)
        else:
            return False

    def getModule(self, moduleName, name = None):
        if(name is None):
            name = moduleName.split("/")[0]
            moduleName = moduleName.split("/")[1]

        if(name in self.__fileWatchers.keys()):
            return self.__fileWatchers[name].getModule(moduleName)
        else:
            return None

    def watch(self):
        try:
            i = 0
            keys = self.__fileWatchers.keys()
            while(True):
                i = i + 1
                self.compileAll()
                time.sleep(2)
                if(i%5 == 0):
                    for name in keys:
                        self.__fileWatchers[name].seekFiles()
        except KeyboardInterrupt:
            print("End of program")
    def compileAll(self):
        start_time = time.time()
        dep = {}
        done = []
        toCompile = []
        for name in self.__fileWatchers.keys():
            toCompile+=self.__fileWatchers[name].getFiles()
        for tsfile in toCompile:
            dep[tsfile.getLongModuleName()] = tsfile.getDependencies()
            tsfile.checkLastDateChanged()
        metaHasCompiled = False
        hasCompiled = True

        errors = 0
        compilations = 0

        error_line = "error"
        module_list = []
        module_list_error = []
        list_error = []
        times = []

        while(hasCompiled):
            hasCompiled = False
            isFailed = False
            for tsfile in toCompile:
                compile = False


                if(not tsfile.isUpToDate()):
                    compile = True
                    module_list.append(tsfile.getLongModuleName())
                    LOG.orange(tsfile.getLongModuleName()+" has changed...")
                else:
                    # LOG.info(file.getModule()+":"+str(file.getLastDate()))
                    compile = False
                    for depend in dep[tsfile.getLongModuleName()]:
                        md5 = tsfile.getDependencyMD5(depend)
                        if(md5!=self.getModule(depend).getMD5() and not self.getModule(depend).isFailed()):
                            compile = True
                            LOG.orange(tsfile.getLongModuleName()+" depends of "+depend+" and has to be recompiled")
                            #LOG.red(md5)
                            #LOG.green(self.getModule(depend).getMD5())
                            break
                if(compile):
                    #LOG.out("Compile "+file.getLongModuleName())
                    success, t = tsfile.compile()
                    times.append(t)
                    if(not success):
                        module_list_error.append(tsfile.getLongModuleName())
                        list_error.append(tsfile.getLastError())
                        LOG.error("Error during compilation of "+tsfile.getLongModuleName())
                        self.__errors = self.__errors + 1
                        errors = errors + 1


                    self.__compilations = self.__compilations + 1
                    compilations = compilations + 1
                    hasCompiled = True
                    metaHasCompiled = True

                    if(success):
                        for module in toCompile:
                            if(module.isFailed()):
                                module.resetFailed(tsfile.getLongModuleName())


        isFailed = False
        for tsfile in toCompile:
            if(tsfile.isFailed()):
                isFailed = True
                break

        if(metaHasCompiled):
            #LOG.green("Step 1 in "+str(round(time.time()-start_time,2))+"s")
                    
            save = {}
            for tsfile in toCompile:
                save[tsfile.getLongModuleName()] = {"dependencies":tsfile.getDependencyMD5(), "errors":tsfile.isFailed(),"last_date":tsfile.getLastDate(),"last_date_compilation":tsfile.getLastCompilationDate()}
            save = json.dumps(save)
            f = open(".cache_metacompile.json","w")
            f.write(save)
            f.close()


            if("compile_modules" in data and data["compile_modules"] == True):
                ##Javascript concatenation for each module

                dep_order = self.getDependenciesInOrder(dep, dep.keys())
                files = {}
                names = {}
                maps = {}
                for name in dep_order:
                    tsfile = self.getModule(name)
                    if(tsfile.getRoot() not in files):
                        files[tsfile.getRoot()] = []
                        maps[tsfile.getRoot()] = []
                        names[tsfile.getRoot()] = [""]  
                    names[tsfile.getRoot()] += [tsfile.getLongModuleName()]
                    files[tsfile.getRoot()] += tsfile.getJSContent(True)
                    maps[tsfile.getRoot()].append(tsfile.getMapFile())
                for name in files:
                    f = open(name+"/index.js",'w')
                    f.write("".join(files[name]))
                    f.write("\n///".join(names[name]))
                    f.write("\n//# sourceMappingURL=index.js.map")
                    f.close()
                    args = ["node",".pythoncompile/node_modules/source-map-concat/bin/source-map-concat.js","--source-file", name+"/index.js", "--out-file",name+"/index.js.map"] + maps[name]
                    #print(" ".join(args))
                    call(args)
                    
                #LOG.green("Step 2 in "+str(round(time.time()-start_time,2))+"s")
            if("out" in data):
                source = False
                if("concat_sourcemaps" in data and data["concat_sourcemaps"] == True):
                    source = True
                for out in data["out"]:
                    module = self.getModule(out)
                    maps = []
                    if(module is not None):
                        dependencies = self.getDependenciesInOrder(dep, module.getAllDependencies()) + [module.getLongModuleName()]
                        writer = open(data["out"][out],'w')
                        for name in dependencies:
                            tsfile = self.getModule(name)
                            maps.append(tsfile.getMapFile())
                            try:
                                writer.write(""+("".join(tsfile.getJSContent(True))))
                            except:
                                LOG.red("/!\ Unable to read "+name+"'s js file - "+data["out"][out]+" can't be correctly created /!\\")
                        if(source):
                            writer.write("\n//# sourceMappingURL="+data["out"][out]+".map")
                        writer.close()
                        if(source):
                            args = ["node",".pythoncompile/node_modules/source-map-concat/bin/source-map-concat.js","--source-file", data["out"][out],"--out-file",data["out"][out]+".map"] + maps
                            call(args)
                        
                #LOG.green("Step 3 in "+str(round(time.time()-start_time,2))+"s")
                    #print(self.getModule(out))
            avg = 0
            if(len(times) > 0):
                for t in times:
                    avg += t
                avg /= len(times)
                avg = round(avg, 2)

            LOG.green("Compiled in "+str(round(time.time()-start_time,2))+"s - average time : "+str(avg)+"s")
            if(isFailed or errors > 0):
                LOG.error("End of step with errors : "+str(compilations)+" compilation(s) and "+str(errors)+" error(s)")
                if(USE_SOUND):
                    Tools.speak(str(errors)+" error")
                    
                if(USE_NOTIFICATION):
                    error_msg = None
                    for index,tsfile in enumerate(module_list_error) :
                        if(error_msg is None):
                            error_msg = ""
                        else:
                            error_msg = error_msg +"\n"
                        line = list_error[index].split("\n")[0]
                        m = re.search('([^/]+\.ts)\(([0-9]+),', line)
                        error_msg = error_msg + tsfile + " "+m.group(1)+":"+m.group(2)
                    
        	    Tools.notify(str(error_msg), str(errors)+" Error(s)", str("\n".join(module_list_error)), "error", "Basso")
                    #os.system("osascript -e 'display notification \""+str(errors)+" Error(s)\" with title \"Error\"'")
            else:
                LOG.green("End of step : "+str(compilations)+" compilation(s) and "+str(errors)+" error(s)")
                if(USE_SOUND):
                    Tools.speak("ok")
                if(USE_NOTIFICATION):
        	    Tools.notify(str("\n".join(module_list)), "Success!", str("\n".join(module_list_error)), "ok", "Purr")
                    #os.system("osascript -e 'display notification \"Success\" with title \"Success\"'")
    def getDependenciesInOrder(self, dep, dep_list):
        dep_order = []
        dep_save = copy.deepcopy(dep)
        i = 0
        j = 0
        while(len(dep_list)>0 and j<100):
            dependency = dep_list[i]
            for done in dep_order:
                if(done in dep_save[dependency]):
                    dep_save[dependency].remove(done)
            if(len(dep_save[dependency]) == 0):
                dep_order.append(dependency)
                dep_list.remove(dependency)
            else:
                i = i + 1
            if(i>=len(dep_list)):
                i = 0
            j = j + 1
            #print(self.getModule(dependency).getJSContent())
                    #print(dependency, len(dep[dependency]),dep[dependency])
        if j>=100:
            raise Exception("Dependencies cycle")
        else:
            return dep_order

class TSFilesWatcher:
    def __init__(self, root, mega, parentModuleName):
        try:
            self.__errors = 0
            self.__compilations = 0
            self.__errors = 0
            self.__root = root
            self.__files = []
            self.__mega = mega
            self.__parentModuleName = parentModuleName
            self.prepareModules()

            self.seekFiles()


            #self.compileAll()

            #self.checkDependenciesAll()

            #self.watch()
        except KeyboardInterrupt:
            print("\n")
            LOG.info("End of program : "+str(self.__compilations)+" compilation(s) and "+str(self.__errors)+" error(s)")
    def getFiles(self):
        return self.__files
    def prepareModules(self):
        for filename in os.listdir(self.__root):
            exists = False
            #pas les fichiers/dossiers caches
            if(filename[0:1]!="."):
                file = os.path.join(self.__root, filename)
                #seulement directories
                if(os.path.isdir(file)):
                    self.prepareModule(self.__root, filename)
                    

    def prepareModule(self, root, filename):
        file = os.path.join(root, filename)
        moduleFile = os.path.join(file,filename+".class.ts")
        #return
        files_dir = []
        files_import = []
        ts_found = os.path.exists(moduleFile)
        if(not ts_found):
            for root, subFolders, files in os.walk(file,followlinks=True):
                if(not ts_found):
                    for f in files:
                        if(f[0:1]!="."):
                            extension = f.split(".")
                            if(extension[-2]!="d" and extension[-1]=="ts" and extension[-2]!="class"):
                                ts_found = True
                                break
        if(ts_found):
            if(not os.path.exists(moduleFile)):
                f = open(moduleFile, "w")
                f.write("\n")
                f.close()

            moduleFile = os.path.join(file,filename+".class.d.ts")
            if(not os.path.exists(moduleFile)):
                f = open(moduleFile, "w")
                f.write("\n")
                f.close()
            
            
    def checkDependenciesAll(self):
        for module in self.__files:
            module.checkDependencies()

    def compileAllDeprecated(self):
        dep = {}
        done = []
        toCompile = []
        toCompile[:] = self.__files
        for file in self.__files:
            dep[file.getModule()] = file.getDependencies()
            file.checkLastDateChanged()

        metaHasCompiled = False
        hasCompiled = True

        errors = 0
        compilations = 0

        error_line = "error"
        module_list = []
        module_list_error = []
        list_error = []

        while(hasCompiled):
            hasCompiled = False
            isFailed = False
            for file in toCompile:
                compile = False


                if(not file.isUpToDate()):
                    compile = True
                    module_list.append(file.getModule())
                    LOG.orange(file.getLongModuleName()+" has changed...")
                else:
                    # LOG.info(file.getModule()+":"+str(file.getLastDate()))
                    compile = False
                    for depend in dep[file.getModule()]:
                        md5 = file.getDependencyMD5(depend)
                        if(md5!=self.getModule(depend).getMD5() and not self.getModule(depend).isFailed()):
                            compile = True
                            LOG.orange(file.getModule()+" depends of "+depend+" and has to be recompiled")
                            break
                if(compile):
                    LOG.out("Compile "+file.getModule())
                    success = file.compile()
                    if(not success):
                        module_list_error.append(file.getModule())
                        list_error.append(file.getLastError())
                        LOG.error("Error during compilation of "+file.getModule())
                        self.__errors = self.__errors + 1
                        errors = errors + 1


                    self.__compilations = self.__compilations + 1
                    compilations = compilations + 1
                    hasCompiled = True
                    metaHasCompiled = True

                    if(success):
                        for module in toCompile:
                            if(module.isFailed()):
                                module.resetFailed(file.getModule())


        isFailed = False
        for file in toCompile:
            if(file.isFailed()):
                isFailed = True
                break

        if(metaHasCompiled):
            if(isFailed or errors > 0):
                LOG.error("End of step with errors : "+str(compilations)+" compilation(s) and "+str(errors)+" error(s)")
                if(USE_SOUND):
                    Tools.speak(str(errors)+" error")
                if(USE_NOTIFICATION):
                    error_msg = None
                    for index,file in enumerate(module_list_error) :
                        if(error_msg is None):
                            error_msg = ""
                        else:
                            error_msg = error_msg +"\n"
                        line = list_error[index].split("\n")[0]
                        m = re.search('([^/]+\.ts)\(([0-9]+),', line)
                        error_msg = error_msg + file + " "+m.group(1)+":"+m.group(2)
                    
        	    Tools.notify(str(error_msg), str(errors)+" Error(s)", str("\n".join(module_list_error)), "error", "Basso")
                    #os.system("osascript -e 'display notification \""+str(errors)+" Error(s)\" with title \"Error\"'")
            else:
                LOG.green("End of step : "+str(compilations)+" compilation(s) and "+str(errors)+" error(s)")
                if(USE_SOUND):
                    Tools.speak("ok")
                if(USE_NOTIFICATION):
        	    Tools.notify(str("\n".join(module_list)), "Success!", str("\n".join(module_list_error)), "ok", "Purr")
                    #os.system("osascript -e 'display notification \"Success\" with title \"Success\"'")


    def watch(self):
        i = 0
        while(True):
            i = i + 1
            self.compileAll()
            time.sleep(2)
            if(i%5 == 0):
                self.seekFiles()


    def seekFiles(self):
        for filename in os.listdir(self.__root):
            #pas les fichiers/dossiers caches
            if(filename[0:1]!="."):
                file = os.path.join(self.__root, filename)
                #seulement directories
                if(os.path.isdir(file)):
                    for subfilename in os.listdir(file):
                        extension = subfilename.split(".")
                        #seulement fichiers ts
                        if(extension[-1] == "ts" and extension[-2]!="d" and extension[-2]=="class"):
                        #if(extension[-1] == "ts" and extension[-2]!="d"):
                            self.__addFile(file, subfilename)

        #remove removed files
        self.__files[:] = [file for file in self.__files if not file.isRemoved()]


    def __addFile(self, modulePath, filePath):
        for file in self.__files:
            if(file.same(self.__root, modulePath, filePath)):
                return
        file = TSFile(self, self.__root, modulePath, filePath)
        self.__files.append(file)
        #file.init()


    def hasModule(self, moduleName, name = None):
        if(name is None or name == self.getParentName()):
            for file in self.__files:
                if(file.isModule(moduleName)):
                    return True
        else:
            return self.__mega.hasModule(moduleName, name)

    def getModule(self, moduleName, name = None):
        if(name is None or name == self.getParentName()):
            for file in self.__files:
                if(file.isModule(moduleName)):
                    return file
        else:
            return self.__mega.getModule(moduleName, name)
    def getParentName(self):
        return self.__parentModuleName
    def getRoot(self):
        return self.__root.split("/")[0]


class MD5File:
    @staticmethod
    def getMD5(path):
        return hashlib.md5(open(path, 'rb').read()).hexdigest().strip()


class Tools:
    @staticmethod
    def cmdExist(name):
        try:
            devnull = open(os.devnull)
            if(isinstance(name, basestring)):
                args = [name]
            else:
                args = name
            subprocess.Popen(args, stdout=devnull, stderr=devnull).communicate()
        except OSError as e:
            if e.errno == os.errno.ENOENT:
                return False
        return True

    @staticmethod
    def speak(text):
        if(Tools.cmdExist(["say", "''"])):
            os.system("say '"+text+"'")

    @staticmethod
    def notify(text, title, subtitle, icon, sound):
        notifySubtitle = ""
        if(sys.platform == 'darwin'):
            if(not Tools.cmdExist("terminal-notifier")):
                os.system("brew install terminal-notifier")

            if(subtitle is not None and len(subtitle.strip()) > 0):
                notifySubtitle = "-substitle '"+subtitle+"'"
            os.system("terminal-notifier -message '"+text+"' "+notifySubtitle+" -title '"+title+"' -activate com.googlecode.iterm2 -sound "+sound+" -group compile")
        else:
            import pynotify
            if not pynotify.init("Typescript compilation"):
                print "Failed to send notification"
            else:
                notifyTitle = title
                if(subtitle is not None and len(subtitle.strip()) > 0):
                    notifyTitle += "\n"+subtitle
                n = pynotify.Notification(notifyTitle, text, "dialog-"+icon)
                n.set_urgency(pynotify.URGENCY_NORMAL)
                n.set_timeout(2500)
                try:
                    if not n.show():
                        print "Failed to send notification"
                except:
                    print "Failed to send notification (restart metatypescript is needed)"
                    pass


class TSFile:
    def __init__(self, watcher, root, module, file):
        self.__watcher = watcher
        self.__removed = False
        self.__root = root;
        self.__module = os.path.relpath(module, root)
        self.__filepath = file
        self.__realPath = os.path.join(self.__root, self.__module, self.__filepath)

        self.__dep = []
        self.__depMD5 = {}

        #self.__dependencies = []
        #self.__dependenciesMD5 = {}
        self.__md5 = ""
        self.__lastDateChanged = None
        self.__lastCompilationDate = None
        self.__failed = False
        self.__last_error = ""

        

    def init(self):
        if(not self.isUpToDate()):
            self.prepare()
        self.checkDependencies()
        if(not self.__removed):
            self.refreshMD5()
            self.checkLastDateChanged()
        
        





    def __unicode__(self):
        return self.__str__()


    def isFailed(self):
        return self.__failed

    def resetFailed(self, moduleName):
        self.__failed = False
        if(moduleName in self.__depMD5):
            self.__depMD5[moduleName] = None

    def prepare(self):
        #LOG.green(self.getLongModuleName()+" prepare")
        index = self.__realPath.rfind(os.path.sep)
        file = self.__realPath[:index]

        index = file.rfind(os.path.sep)
        filename = file[index+1:]
        root = file[:index]
        index = root.rfind(os.path.sep)
        root = root[:index]

        moduleFile = os.path.join(file,filename+".class.ts")
        if(os.path.exists(moduleFile)):
            pass
        #return
        files_dir = []
        files_import = []
        lib_import = []
        module_not_in_d_ts = []
        module_to_copy = []
        for root, subFolders, files in os.walk(file,followlinks=True):
            for f in files:
                if(f[0:1]!="."):
                    extension = f.split(".")
                    if(extension[-2]!="d" and extension[-1]=="ts"):
                        if(os.path.relpath(os.path.join(root,f)) == moduleFile):
                            continue
                        fileread = open(os.path.join(root,f), "r")
                        
                        excluded = False
                        
                        for line in fileread:
                            result = REGEXP_CUSTOM.match(line)
                            if(result != None):
                                type = result.group(1)
                                if(type == "exclude"):
                                    LOG.orange(os.path.join(root,f)+" is excluded")
                                    excluded = True
                                    break
                                else:
                                    LOG.red(type+" of reference is not understood")

                            else:
                                reg = REGEXP_IMPORT_CUSTOM.match(line)
                                if(reg!=None):
                                    type = reg.group(1)
                                    result = reg.group(2)
                                    if(type == "module"):
                                        include_in_d_ts = True
                                        copy_in_js = False
                                        if(len(reg.groups())>=3):
                                            if(reg.group(3)=="first"):
                                                include_in_d_ts = False
                                            elif(reg.group(3)=="copy"):
                                                copy_in_js = True
                                        #import d'un module ou parent-module
                                        module_file = result
                                        parts = module_file.split("/")
                                        if(len(parts)>2):
                                            grand_parent = parts[0]
                                            parts.pop(0)
                                        else:    
                                            grand_parent = self.__watcher.getRoot()

                                        if(len(parts)>1):
                                            parent = parts[0]
                                            module = parts[1]
                                        else:
                                            parent = self.__watcher.getParentName()
                                            module = parts[0]

                                        if(copy_in_js and module_file not in module_to_copy):
                                            module_to_copy.append(parent+"/"+module)
                                        if(include_in_d_ts):
                                            module_file = module+".class.d.ts"
                                        else:
                                            module_file = module+".class_free.d.ts"


                                        if(parent == self.__watcher.getParentName()):
                                              module_file = ".."+os.path.sep+module+os.path.sep+module_file  
                                        else:
                                            
                                            if(grand_parent == self.__watcher.getRoot()):
                                                module_file = ".."+os.path.sep+".."+os.path.sep+parent+os.path.sep+module+os.path.sep+module_file
                                            else:#two folders top
                                                module_file = ".."+os.path.sep+".."+os.path.sep+".."+os.path.sep+grand_parent+os.path.sep+parent+os.path.sep+module+os.path.sep+module_file

                                        if(module_file not in files_import):
                                            files_import.append(module_file)
                                        if(not include_in_d_ts and module_file not in module_not_in_d_ts):
                                            module_not_in_d_ts.append(module_file)
                                        
                                    elif(type == "file"):
                                        #import file (for import order)
                                        module_file = result
                                        if(module_file[-3:]!=".ts"):
                                            module_file += ".ts"
                                        if(module_file not in files_dir):
                                            files_dir.append(module_file)
                                    elif(type == "lib"):
                                        #import d'une librairie
                                        module_file = ".."+os.path.sep+".."+os.path.sep+".."+os.path.sep+"lib"+os.path.sep+result+os.path.sep+result+".d.ts"
                                        if(module_file not in lib_import):
                                            lib_import.append(module_file)

                                    else:
                                        LOG.red(type+" of reference is not understood")

                                else:
                                    result = REGEXP_IMPORT_D_TS_IMPORT.match(line)
                                    if(result!=None):
                                        fileimported = result.group(1)
                                        for i in range(0, os.path.relpath(os.path.join(root,f),file).count(os.path.sep)):
                                            fileimported = fileimported[3:]
                                        if(fileimported not in files_import):
                                            files_import.append(fileimported)
                                        continue
                        fileread.close()
                        if(not excluded):
                            file_test = os.path.relpath(os.path.join(root,f),file)
                            if(file_test not in files_dir):
                                files_dir.append(file_test)
        if(len(lib_import)>0):
            content = "/* Librairies Externes */\n"
            for line in lib_import:
                content += "///<reference path=\""+line+"\"/>\n"
        else:
            content = ""

        if(len(files_import)>0):
            if(len(content)>0):
                content+="\n"
            content += "/* Modules Externes */\n"
            for line in files_import:
                content+= "///<reference path=\""+line+"\"/>\n"
        if(len(files_dir)>0):
            if(len(content)>0):
                content+="\n"
            content += "\n/* Fichiers Internes */\n"
            for line in files_dir:
                content+= "///<reference path=\""+line+"\"/>\n"

        f = open(moduleFile, "w")
        f.write(content)
        f.close()
        return (module_not_in_d_ts, files_import, module_to_copy)

    def compile(self):
        start_time = time.time()
        module_not_in_d_ts, files_import, module_to_copy = self.prepare()
        start_time2 = time.time()
        try:
            global TYPESCRIPT_PATH
            #args = ["tsc", "-t","ES"+str(ESVersion), "--declaration", "--sourcemap", self.__realPath, "--out", self.__realPath[:-2]+"js"]
            #args = ["tsc", "-t","ES"+str(ESVersion), "--declaration", "--sourcemap", self.__realPath, "--out", self.__realPath[:-2]+"js"]
            #
            #
            
            #LOG.red(path)
            args = TYPESCRIPT_PATH + ["-t","ES"+str(ESVersion), "--declaration", "--sourcemap", self.__realPath, "--out", self.__realPath[:-2]+"js"]
            #print(" ".join(args))
           # print(args)
            pipe = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except:
            LOG.error("Typescript is not installed - please execute:")
            LOG.error("npm -g install typescript")
            LOG.red(sys.exc_info()[0])
            sys.exit(1)
            return
        output, errors = pipe.communicate()
        #pipe.wait()
        
        start_time2 = round(time.time()-start_time2,2)
        if(errors is None or len(errors)==0):
            if(output.find("error")!=-1):
                errors = output
        #print(start_time2)
        if(errors!=None and len(errors)>0):
            self.__last_error = errors
            
            LOG.error("["+os.path.join( self.getLongModuleName(), self.__filepath)+"]:\n"+str("\n".join(errors.split("\n")[0:5])).replace(os.path.abspath(self.__root),""))
            self.__failed = True
            self.refreshMD5()
            self.checkLastDateChanged()
            self.checkDependencies()
            self.__lastCompilationDate = self.__lastDateChanged
            self.__refreshDepMD5()
        else:
            self.__failed = False
            
            file = open(self.__realPath[:-2]+"d.ts","r")
            file_content = ""
            file_content_free = ""
            for line in file:
                #print(line)
                result = REGEXP_IMPORT_D_TS.match(line)
                    
                #TODO:check si le module est bien un module typescript a nous
                if(result is None or result.group(1) not in module_not_in_d_ts):
                    file_content = file_content + "\n" + line
                if(result is None or result.group(1) not in files_import):
                    file_content_free = file_content_free + "\n" + line
                
            file.close()
            file = open(self.__realPath[:-2]+"d.ts","w")
            file.write(file_content)
            file.close()
            file = open(self.__realPath[:-3]+"_free.d.ts","w")
            file.write(file_content_free)
            file.close()
            #print(round(time.time()-start_time,2))
            if(len(module_to_copy)>0):
                content = ""
                file = open(self.__realPath[:-2]+"js","r")
                for line in file:
                    content+= line+"\n"
                file.close()
                content_imported = "var fs = require(\"fs\");\n"
                dep = []
                for name in module_to_copy:
                    if(name not in dep):
                        
                        #dep.append(name)
                        moduleDep = self.__getAllDependencies(name)
                        #LOG.red(name)
                        #LOG.green(moduleDep)
                        for dependency in moduleDep:
                            if(dependency not in dep):
                                dep.append(dependency)
                #dep.reverse()
                for name in dep:
                    module = self.__watcher.getModule(name.split("/")[1],name.split("/")[0])
                    content_imported+='eval(fs.readFileSync("../../'+name+'/'+module.getModule()+'.class.js").toString());\n'

                content = content_imported + content
                file = open(self.__realPath[:-2]+"js","w")
                file.write(content)
                file.close()
                

            self.checkLastDateChanged()
            self.refreshMD5()
            self.checkDependencies()
            self.__refreshDepMD5()
            self.__lastCompilationDate = self.__lastDateChanged
        start_time = round(time.time()-start_time,2)
        LOG.blue("Compiled in "+str(start_time)+"s ("+str(start_time2)+"s)")
        return (not self.__failed,start_time)


   
    def getJSContent(self, clean = False):
        file = open(self.__realPath[:-2]+"js","r")
        lines = []
        for line in file:
            if(clean):
                if(line.find("//# sourceMappingURL")!=-1):#/* or line.find("///<reference path")!=-1
                    continue
            lines.append(line)
        file.close()
        return lines

    def getMapFile(self):
        return self.__realPath[:-2]+"js.map"

    def __getAllDependencies(self, longName = None, original = []):
        if( longName is None):
            module = self
        else:
            module = self.__watcher.getModule(longName.split("/")[1],longName.split("/")[0])
        if(module is not None and longName not in original):
            dep = module.getDependencies()
            if(len(dep)>0):
                if(longName not in original and module is not self):
                    original.append(longName)
                for dependency in dep:
                    if(dependency not in original):
                        self.__getAllDependencies(dependency, original)
            else:
                if(module is not self):
                    original.append(longName)
        return original
    
    def getAllDependencies(self):
        return self.__getAllDependencies()


    def getLastDate(self):
        return self._lastDateChanged

    def getLastCompilationDate(self):
        return self.__lastCompilationDate   

    def setLastDate(self, date):
        self.__lastDateChanged = date

    def setLastCompilationDate(self, date):
        self.__lastCompilationDate = date

    def isUpToDate(self):
        return self.__lastDateChanged!=None and self.__lastCompilationDate >= self.__lastDateChanged

    def isFailed(self):
        return self.__failed

    def isModule(self, moduleName):
        return moduleName == self.__module

    def getLastError(self):
        return self.__last_error

    def getRoot(self):
        return self.__root

    def getModule(self):
        return self.__module

    def getLongModuleName(self):
        return self.__watcher.getParentName()+"/"+self.getModule()

    def getLastDate(self):
        return self.__lastDateChanged

    def getDependencies(self):
        return self.__dep

    def getDependencyMD5(self, module = None):
        if(module is not None):
            return self.__depMD5[module]
        return  self.__depMD5
    def setDependencyMD5(self, dependencies):
        self.__depMD5 = dependencies

    def setError(self, error):
        self.__failed = error

    def same(self, root, module, file):
        module = os.path.relpath(module, root)
        return root==self.__root and module == self.__module and file == self.__filepath

    def checkLastDateChanged(self):
        dir = os.path.join(self.__root, self.__module)
        date = os.path.getmtime(dir)
        #print(dir+":"+str(date))
        for dirpath, dirnames, filenames in os.walk(dir, None, True):
            for subdirname in dirnames:

                sdate = os.path.getmtime(os.path.join(dirpath, subdirname))
                
                if(sdate>date):
                    date = sdate
            for subdirname in filenames:
                sdate = os.path.getmtime(os.path.join(dirpath, subdirname))
                
                if(sdate>date):
                    date = sdate
        self.__lastDateChanged = date
        

    def checkDependencies(self):
        file = None

        try:
            file = open(self.__realPath, 'r')
            #dep = []
        except(IOError):
            LOG.error("Can't read "+self.__filepath)

        #reset des dependances
        self.__dep = []

        if(file != None):
            for line in file:
                result = REGEXP_IMPORT.match(line)
                if(result!=None):
                    depModule = result.group(2)
                    
                    #dep.append(depModule)
                    #is not None: pour les dossier n'etant pas des modules
                    #LOG.green(depModule)
                    if(result.group(1) == ".."):
                        self.__addDependency(depModule, self.__watcher.getParentName())
                        #if (depModule not in self.__dependencies and self.__watcher.getModule(depModule) is not None):
                        #    self.__dependencies.append(module.getParentName()+"/"+depModule)
                        #    self.__dependenciesMD5[module.getParentName()+"/"+depModule] = None
                    else:
                        self.__addDependency(depModule, result.group(1).split(os.path.sep)[-1])
                        #mega module bof
                        #pass
                        ##if (depModule not in self.__dependenciesMEGA and self.__watcher.getModule(depModule, result.group(1)) is not None):
                            #pass
                            #self.__dependenciesMEGA[result.group(1)].append(depModule)
                            #self.__dependenciesMEGAMD5[result.group(1)][depModule] = None

            file.close()
            #self.__dependencies[:] = [modep for modep in self.__dependencies if modep in dep]
            if(len(self.__dep)>0):
                LOG.blue(self.getLongModuleName()+" Dependencies : "+LOG.getColor('ORANGE')+str(self.__dep))
        else:
            self.__removed = True

    def __addDependency(self, module, parentName):
        long_name = parentName+"/"+module
        if(long_name not in self.__dep and self.__watcher.getModule(module, parentName) is not None):
            self.__dep.append(long_name)
            if(long_name not in self.__depMD5.keys()):
                self.__depMD5[long_name] = None

    def getMD5(self):
        return self.__md5

    def refreshMD5(self):
        self.__md5 = MD5File.getMD5(self.__realPath[:-2]+"d.ts")

    def __refreshDepMD5(self):
        for dep in self.__dep:
            module = dep.split("/")[1]
            parentName = dep.split("/")[0]
            if(self.__watcher.hasModule(module, parentName )):
                self.__depMD5[dep] = self.__watcher.getModule(module, parentName ).getMD5()

    def isRemoved(self):
        return self.__removed

    def __str__(self):
        valueStr = "[TSFile module=\""+self.__module+"\" file=\""+self.__filepath+"\" root=\""+self.__root+"\" md5=\""+str(self.__md5)+"\""
        return  valueStr+" dep=\""+str(len(self.__dep))+"\" upToDate=\""+str(self.isUpToDate())+"\"]"

    def __repr__(self):
        return self.__str__()


def initialize():
    LOG.green("initiliazing project")
    if(Tools.cmdExist("git")):
        os.system("git clone https://github.com/borisyankov/DefinitelyTyped.git lib")
    #distutils.shutil.copytree()
    source_example = os.path.abspath(os.path.dirname(os.path.realpath(__file__))+os.sep+".."+os.sep+"example")
    copytree(source_example, ".")
    

def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        try:
            if os.path.isdir(s):
                shutil.copytree(s, d, symlinks, ignore)
            else:
                shutil.copy2(s, d)
        except:
            LOG.red(d+" already exists or can't be written")
if __name__ == '__main__':
    LOG = Console()
    LOG.info("Typescript Start")
    #LOG.green(sys.argv[0])
    #LOG.red(os.getcwd())
    #
    if(TYPESCRIPT_PATH is None):
        if(Tools.cmdExist("tsc")):
            TYPESCRIPT_PATH = ["tsc"]
        else:
            path = os.path.dirname(os.path.realpath(__file__))
            path = os.path.join(path, "../")
            TYPESCRIPT_PATH = ["node", path+"node_modules/typescript/bin/tsc.js" ]
        LOG.green("Typescript version:")
        subprocess.call(TYPESCRIPT_PATH+["-v"])

    if(not os.path.isfile('metatypescript.json')):
        LOG.orange("No metatypescript.json file found - initializing a new project")
        initialize()
    try:
        file_config=open('metatypescript.json','r')
    except:
        LOG.red(os.getcwd()+"/metatypescript.json not found")
        sys.exit(1)
    data = json.load(file_config)
    
    file_config.close()
    initialize = False

    directory = data["folders"][0]
    try:
        opts, args = getopt.getopt(sys.argv[1:], "d:es5:ns:nn:init:R", ["directory=","es5","nosound","nonotification","initialize","reset"])
        for o, a in opts:
            if o in ("-d", "--directory"):
                directory = a
            elif o in ("-es5", "--es5"):
                ESVersion = 5
            elif o in ("-ns","--nosound"):
                USE_SOUND = False
            elif o in ("-nn","--nonotification"):
                USE_NOTIFICATION = False
            elif o in ("-init","--initialize"):
                initialize = True
            elif o in ("-R","--reset"):
                os.remove(".cache_metacompile.json");

    except getopt.GetoptError as err:
        LOG.error(err)
    if(initialize):
        initialize()

    MegaWatcher(data["folders"])
    exit(1)
    for folder in data["folders"]:
        if(not os.path.exists(folder)): 
            LOG.error(folder+" not found")
            exit(1)
        LOG.info("Reading "+folder+" folder")
        if(not os.path.exists(os.path.join(folder,".tmp"))):
            os.mkdir(os.path.join(folder,".tmp"), 0777)
        watcher = TSFilesWatcher(folder)
