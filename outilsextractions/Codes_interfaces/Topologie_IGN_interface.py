
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 27 11:23:35 2022

@author: Sami
"""

#==============================================================================
# Modules à importer : NE PAS TOUCHER
#==============================================================================

import sys
import os
import qgis.utils
import processing
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtWidgets import *
from pyproj import Transformer
from PyQt5.QtWidgets import QLineEdit, QFileDialog
from PyQt5.QtCore import Qt
import numpy as np
import shutil

#==============================================================================
# Interface et paramètres du script
#==============================================================================

class DroppableLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                self.setText(file_path)
        else:
            super().dropEvent(event)


#Classe pour la création de l'interface utilisateur et attribution de valeurs initiales
class ParametresDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Paramètres Topologie")
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # Créer un widget de conteneur pour le contenu de la boîte de dialogue
        container_widget = QWidget()
        self.layout = QVBoxLayout(container_widget)
        
        self.fields_layout = QVBoxLayout()
        self.nom_tuiles = {}
        
        self.chemin_vers_dossier_tuiles_label = QLabel("Chemin d'accès au dossier des tuiles : ")
        self.chemin_vers_dossier_tuiles_button = QPushButton("Sélectionner un dossier")
        self.chemin_vers_dossier_tuiles_button.setFixedSize(170, 25)
        self.chemin_vers_dossier_tuiles_edit = DroppableLineEdit()
        
        self.chemin_vers_dossier_tuiles_button.clicked.connect(lambda : self.select_folder(self.chemin_vers_dossier_tuiles_edit))
        
        self.layout.addWidget(self.chemin_vers_dossier_tuiles_label)
        self.layout.addWidget(self.chemin_vers_dossier_tuiles_edit)
        self.layout.addWidget(self.chemin_vers_dossier_tuiles_button)
        
        self.nom_tuiles_label = QLabel("Rentrez le nom de la tuile ou des tuiles considérées: ")
        self.layout.addWidget(self.nom_tuiles_label)

        self.add_field_button = QPushButton("Ajouter une tuile")
        self.add_field_button.setFixedSize(150, 30)
        self.add_field_button.clicked.connect(self.add_field)
        self.fields_layout.addWidget(self.add_field_button)
        self.layout.addLayout(self.fields_layout)
        
        self.epsg_label = QLabel("EPSG (Rentrez le code du système de coordonnées souhaité (si inconnu, le chercher sur Google)): ")
        self.epsg_edit = QLineEdit()
        self.layout.addWidget(self.epsg_label)
        self.layout.addWidget(self.epsg_edit)
        
        self.dossier_sortie_label = QLabel("Chemin d'accès au dossier où les résultats seront enregistrés : ")
        self.dossier_sortie_button = QPushButton("Sélectionner un dossier")
        self.dossier_sortie_button.setFixedSize(170, 25)
        self.dossier_sortie_edit = DroppableLineEdit()
        
        self.dossier_sortie_button.clicked.connect(lambda : self.select_folder(self.dossier_sortie_edit))
        
        self.layout.addWidget(self.dossier_sortie_label)
        self.layout.addWidget(self.dossier_sortie_edit)
        self.layout.addWidget(self.dossier_sortie_button)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok| QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.ok_button = self.buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        
        # Définir le widget de conteneur comme widget du QScrollArea
        scroll_area.setWidget(container_widget)

        # Créer un layout principal pour la boîte de dialogue et ajouter le QScrollArea
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(self.buttons)
        self.setLayout(main_layout)
        self.resize(650, 500)
        
        self.chemin_vers_dossier_tuiles_edit.textChanged.connect(self.check_inputs)
        self.epsg_edit.textChanged.connect(self.check_inputs)
        self.dossier_sortie_edit.textChanged.connect(self.check_inputs)
    
    def select_folder(self, dossier_edit):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if folder:
            dossier_edit.setText(folder)

    def add_field(self):
        new_field = QHBoxLayout()
        new_field_edit = QLineEdit()
        
        button_supprimer = QPushButton("Supprimer")
        button_supprimer.clicked.connect(lambda: self.remove_field(new_field_edit, button_supprimer))
        
        new_field.addWidget(new_field_edit)
        new_field.addWidget(button_supprimer)
        
        self.fields_layout.insertLayout(self.fields_layout.count() - 1, new_field)
        new_field_edit.textChanged.connect(self.check_inputs)
        self.check_inputs()
        
    def remove_field(self, *widgets):
        for field_widget in widgets:
            self.fields_layout.removeWidget(field_widget)
            field_widget.deleteLater()
        self.check_inputs()
    
    def check_inputs(self):
        all_fields_filled = bool(self.chemin_vers_dossier_tuiles_edit.text() and 
            self.epsg_edit.text() and 
            self.dossier_sortie_edit.text())
         
        additional_fields_filled = True 
        for i in range(self.fields_layout.count()):
                field_layout = self.fields_layout.itemAt(i).layout()
                if field_layout:
                    text_field = field_layout.itemAt(0).widget()
                    additional_fields_filled =bool(additional_fields_filled and text_field.text())
        all_fields_filled = bool(all_fields_filled and additional_fields_filled)
        self.ok_button.setEnabled(all_fields_filled)
    
    def getParametres(self):
        chemin_vers_dossier_tuiles = self.chemin_vers_dossier_tuiles_edit.text()
        EPSG_souhaite = int(self.epsg_edit.text())
        dossier_sortie = self.dossier_sortie_edit.text()
        
        indice = 1 
        for i in range(self.fields_layout.count()):
            field_layout = self.fields_layout.itemAt(i).layout()
            if field_layout:
                text_field = field_layout.itemAt(0).widget()
                self.nom_tuiles[indice] = text_field.text()
                indice+=1
                
        return chemin_vers_dossier_tuiles, EPSG_souhaite, dossier_sortie, self.nom_tuiles

# Classe pour les messages d'erreur, peu important dans le code
class MyDialog(QDialog):
    def __init__(self):
        dlg=QDialog.__init__(self)
        self.edit = QTextEdit(dlg)
        self.message="Message temporaire"
        self.edit.setText(self.message)
        self.bar = QgsMessageBar()
        self.bar.setSizePolicy( QSizePolicy.Minimum, QSizePolicy.Fixed )
        self.setLayout(QGridLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok)
        self.buttonbox.accepted.connect(self.run)
        self.layout().addWidget(self.buttonbox, 0, 0, 2, 1)
        self.layout().addWidget(self.bar, 0, 0, 2, 2)
        self.layout().addWidget(self.edit)

    def run(self):
        self.bar.pushMessage("Attention",self.message, level=Qgis.Critical)
        self.edit.setText(self.message)


#==============================================================================
# Corps du script
#==============================================================================

def Topologie():
    param_dialog = ParametresDialog()
    if param_dialog.exec_() == QDialog.Accepted:
        chemin_vers_dossier_tuiles, EPSG_souhaite, dossier_sortie, nom_tuiles = param_dialog.getParametres()
        chemin_vers_dossier_tuiles.encode("cp1252")
        dossier_sortie.encode('cp1252')
    else: 
        myDlg = QMessageBox()
        myDlg.setText( """Les variables initiales n'ont pas été correctement initialisées.

Veuillez réessayer en inscrivant correctement toutes les variables.""")
        myDlg.exec_()
        return  
    
    #Si utilisation parcelles n'est pas 0 ou 1 on arrête tout.
    if not os.path.isdir(chemin_vers_dossier_tuiles):
        myDlg = MyDialog()
        myDlg.message="""Le chemin vers le dossier des tuiles n'est pas correct.
                         Vérifiez que le fichier est toujours à la bonne place, et 
                         attention aux fautes de frappes !"""
        myDlg.show()
        myDlg.run()
        return 

    path_resultats = os.path.join(dossier_sortie, "Resultats_topologie_IGN")
    #Si le dossier n'existe pas, on le crée
    if not os.path.isdir(path_resultats):
            os.mkdir(path_resultats)
    else :
        reply = QMessageBox()
        reply.setText("""Dossier résultat déjà existant. Pour ne pas mélanger les couches, il faut un dossier vierge.\n
          Le dossier va donc être vidé. Si vous voulez d'abord sauvegarder le contenu actuel, appuyez sur 'Non'.\n
            Puis relancez le script.""")
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reply.setDefaultButton(QMessageBox.No)
        x = reply.exec_()
        if x == QMessageBox.Yes:
            shutil.rmtree(path_resultats)
            os.mkdir(path_resultats)

    for i in range(0,len(nom_tuiles.items())):
        fichier_asc =os.path.join(chemin_vers_dossier_tuiles, nom_tuiles[i+1])
        if not os.path.isfile(fichier_asc):
            myDlg = MyDialog()
            myDlg.message="""La tuile %s n'est pas dans le dossier chemin_tuile.
                            Il faut la mettre, ou modifier les tuiles de relief demandées
                            dans la variable nom_tuiles.""" %(nom_tuiles[i+1])
            myDlg.show()
            myDlg.run()
            return 


    outputfile=os.path.join(path_resultats,nom_tuiles[1][:-4]+'_converted.xyz')
    points = []
    for i in range(0,len(nom_tuiles.items())):

        fichier_asc =os.path.join(chemin_vers_dossier_tuiles, nom_tuiles[i+1])
        fichier_asc.encode("cp1252")
        file_directory=fichier_asc.split("\\")[:-1]
        transformer = Transformer.from_crs(2154, EPSG_souhaite)
        
        xcenter = 0
        ycenter = 0
        par=open(fichier_asc)
        z_coord=np.loadtxt(fichier_asc,skiprows=6)
        output=open(outputfile,'w')
        n_cols=int(par.readline().split()[1])
        n_rangs=int(par.readline().split()[1])
        x_lower_left=float(par.readline().split()[1])
        y_lower_left=float(par.readline().split()[1])
        cell_size=float(par.readline().split()[1])
        nan_val=(par.readline().split()[1])
        lons=[]
        lats=[]
        
        for i in range(n_cols):
            lons.append(x_lower_left-xcenter)
            x_lower_left+=cell_size
        
        for i in range(n_rangs):
            lats.append(y_lower_left+cell_size*(n_rangs-1)-ycenter)
            y_lower_left-=cell_size
        
        for i in range(n_rangs):
            for j in range(n_cols):
                points.append((lons[i], lats[j],z_coord[j,i]))


    if (EPSG_souhaite-2154)==0:
        for point in points : 
            output.write('{:3.4f} {:3.4f} {:3.4f}'.format(point[0],point[1],point[2])+'\n')

    else :
        new_points =  transformer.itransform(points)
        for point in new_points : 
            output.write('{:3.4f} {:3.4f} {:3.4f}'.format(point[0],point[1],point[2])+'\n')
    output.close()

if __name__=="__main__":
    Topologie()
