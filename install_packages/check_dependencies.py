import os
import sys
import importlib
from qgis.PyQt.QtWidgets import QMessageBox


def check(required_packages):
    # Check if required packages are installed
    missing_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        message = "Les librairies Python suivantes sont requises pour utiliser le plugin OutilsExtractions:\n\n"
        message += "\n".join(missing_packages)
        message += "\n\nSouhaitez-vous les installer maintenant ? Après l'installation, veuillez redémarrer QGIS."

        reply = QMessageBox.question(None, 'Missing Dependencies', message,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            return

        for package in missing_packages:
            update = False
            try:
                os.system('"' + os.path.join(sys.prefix, 'scripts', 'pip') + f'" install {package}')
                update = True
            finally:
                if not update:
                    try:
                        importlib.import_module(package)
                        import subprocess
                        subprocess.check_call(['python3', '-m', 'pip', 'install', package])
                    except:
                        importlib.import_module(package)
