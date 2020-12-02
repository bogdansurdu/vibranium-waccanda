import argparse
import os
import sys
import configparser
import glob
import requests

class Vibranium:

    def __init__(self):

        # Set WACCANDA endpoint
        self.api = 'http://localhost:3000/api/'

        # Check if $WACC_HOME is set
        try:
            os.environ['WACC_HOME']
        except KeyError:
            print("ERROR: $WACC_HOME environment variable not set! Is the WACC compiler installed correctly?")
            exit(1)

        # Then commence business as usual
        parser = argparse.ArgumentParser(description='The Vibranium package manager for the WACC language.',
            usage='''vibranium <command> [<args>]
            
Valid commands:
init        set up a Vibranium project
install     install a package
remove      remove a package
compile     compile a project''')
        parser.add_argument('command', metavar='command', type=str, help='the command you wish to run.')
        
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unknown command!')
            parser.print_help()
            exit(1)

        # Dispatch command
        getattr(self, args.command)()

    def init(self):
        """ Initialise folder structure and config file"""
        try:
            os.mkdir('.installed_packages')
        except FileExistsError:
            print("WARNING: It seems that the package directory has already been initialised!")
        
        # Create installed packages directory
        if not os.path.exists('.installed_packages/package.directory'):
            with open('.installed_packages/package.directory', 'w+') as f:
                f.write('')
                f.close()

        # Create main file
        if not os.path.exists('main.wacc'):
            with open('main.wacc', 'w+') as f:
                f.write('begin\nskip\nend')
                f.close()

        # Configure config
        cp = configparser.ConfigParser()
        cp['SETTINGS'] = {'entrypoint': 'main.wacc',
                          'output_dir': 'out'}
        cp['DEPENDENCIES'] = {}
        with open('vibranium.config', 'w+') as f:
            cp.write(f)
            f.close()

        print("Initialisation successful!")

    def install(self):
        """ Installs a package """
        parser = argparse.ArgumentParser(description='Installs packages')
        parser.add_argument('package', metavar='package', help='package name. leave empty to install all dependencies.', nargs='*')
        parser.add_argument('--save', '-s', default=False, action='store_true', 
            help='should the package be saved to the requirements?')
        args = parser.parse_args(sys.argv[2:])
        packages = args.package

        # Install requirements
        if len(packages) == 0:
            cp = configparser.ConfigParser()
            cp.read('vibranium.config')
            deps = list(cp['DEPENDENCIES'].items())
            packages = ['{}=={}'.format(p,v) for (p,v) in deps]

        # Otherwise, business as usual
        print('Installing ' + ', '.join(packages))
        # Open package directory
        if not os.path.exists('.installed_packages/package.directory'):
            print("ERROR: Cannot find package directory! Has the project been initalised properly?")
            exit(1)
        cp = configparser.ConfigParser()
        cp.read('.installed_packages/package.directory')
        
        # Check if we already have the package
        for package in packages:
            version = 'latest'
            if '==' in package:
                version = package.split('==')[1]
                package = package.split('==')[0]
            if package in cp.keys():
                p = cp[package]
                if (p['version'] == version):
                    print('Package already present!')
                    exit(0)
            
            # Download the package!
            url = self.api + 'install/{}/{}'.format(package, version)
            r = requests.post(url)

            # Check if found
            if r.content == b'missing':
                print('ERROR: package "{}" has gone missing on our server!'.format(package))
                exit(1)
                
            if r.content == b'not found':
                print('ERROR: package "{}=={}" couldn\'t be found!'.format(package, version))
                exit(1)

            # Write to packages
            dpath = '.installed_packages/{}.wacc'.format(package)
            with open(dpath, 'wb+') as f:
                f.write(r.content)
                f.close()

            # Update package directory
            cp[package] = {
                'version': 'latest',
                'path': dpath
            }
            with open('.installed_packages/package.directory', 'w+') as f:
                cp.write(f)
                f.close()
            if args.save:    
                cp = configparser.ConfigParser()
                cp.read('vibranium.config')
                cp['DEPENDENCIES'][package] = version
                with open('vibranium.config', 'w') as f:
                    cp.write(f)
                    f.close()
                    
            print("INSTALL SUCCESS!")

    def remove(self):
        """ Removes a package """
        parser = argparse.ArgumentParser(description='Removes packages')
        parser.add_argument('package', metavar='package', help='Package name', nargs='+')
        parser.add_argument('--save', '-s', default=False, action='store_true', 
            help='Should the package be removed from the requirements?')
        args = parser.parse_args(sys.argv[2:])

        print('removing')
        if args.save:
            print('saving')

    def compile(self):
        """ Compiles a program """
        cwd = os.getcwd()
        # Check if is valid project
        if not os.path.exists(os.path.join(cwd, 'vibranium.config')):
            print("ERROR: this is not a valid vibranium project")
            exit(1)

        # Read config
        cp = configparser.ConfigParser()
        cp.read('vibranium.config')

        # Get subdirs to include
        includePaths = [x[0] for x in os.walk(cwd)]
        includePathsArg = ' '.join(includePaths)
        
        # Get install folder for self
        install_dir = os.path.dirname(os.path.realpath(__file__))
        ass = 'sh ' + os.path.join(install_dir, 'assemble.sh')
        comp = 'sh ' + os.path.join(install_dir, 'compile.sh')
        link = 'sh ' + os.path.join(install_dir, 'link.sh')
        
        # Create build directory
        output_dir = 'build'
        try:
            output_dir = cp['SETTINGS']['output_dir']
        except KeyError:
            print("ERROR: config doesn't define 'output_dir'!")
            exit(1)

        if os.path.exists(output_dir):
            os.system('rm -r ' + output_dir)
        os.mkdir(output_dir)

        # Get files to compiled
        filesToCompile = []
        for r, _, f in os.walk(os.getcwd()):
            for file in f:
                if '.wacc' in file:
                    filesToCompile.append(os.path.join(r, file))

        # Get a list of any existing assembler files
        sFiles = set(glob.glob('*.s'))

        # Compile all of them
        for f in filesToCompile:
            print('Compiling {}...'.format(f))
            returnCode = os.system(comp + ' ' + f + ' ' + includePathsArg)
            if returnCode != 0:
                print('COMPILE FAILED!')
                exit(1)

        # Find all new ASM files 
        sFiles = set(glob.glob('*s')) - sFiles 

        # Assemble the files
        for f in sFiles:
            print('Assembling {}...'.format(f))
            returnCode = os.system(ass + ' ' + f + ' ' + os.path.join(output_dir, f[:-1] + 'o'))
            if returnCode != 0:
                print('COMPILE FAILED!')
                exit(1)

        # Kill the baby ASM files
        os.system('rm ' + ' '.join(sFiles))

        # Link the files
        print('Linking objects...')
        oFiles = glob.glob(os.path.join(output_dir, '*.o'))
        returnCode = os.system(link + ' ' + os.path.join(output_dir, 'main') + ' ' + ' '.join(oFiles))
        if returnCode != 0:
            print('COMPILE FAILED!')
            exit(1)
            
        # Success!
        print("COMPILE SUCCEEDED!")

if __name__ == '__main__':
    Vibranium()