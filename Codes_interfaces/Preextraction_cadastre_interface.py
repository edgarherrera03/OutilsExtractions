# -*- coding: utf-8 -*-
"""
Created on Wed Apr 27 11:23:35 2022

@author: Sami
"""

"""Ce code sert à extraire le cadastre afin de pouvoir tracer précisément l'emprise 
du projet sans avoir à stocker de couche en local et sans ralentir QGIS"""

#==============================================================================
# Modules à importer : NE PAS TOUCHER
#==============================================================================

import os 
import sys
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtWidgets import *
from PyQt5.QtWidgets import QLineEdit, QFileDialog
from PyQt5.QtCore import Qt
import processing
import requests, zipfile, io
import shutil
import numpy as np
import re

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
        self.setWindowTitle("Paramètres extraction cadastres")
        layout = QVBoxLayout()
        
        self.dossier_resultats_label = QLabel("Chemin d'accès au dossier résultats : ")
        self.dossier_resultats_button = QPushButton("Sélectionner un dossier")
        self.dossier_resultats_button.setFixedSize(170, 25)
        self.dossier_resultats_edit = DroppableLineEdit()
        
        self.dossier_resultats_button.clicked.connect(lambda : self.select_folder(self.dossier_resultats_edit))
        
        layout.addWidget(self.dossier_resultats_label)
        layout.addWidget(self.dossier_resultats_edit)
        layout.addWidget(self.dossier_resultats_button)
        
        self.epsg_label = QLabel("EPSG (Rentrez le code du système de coordonnées souhaité (si inconnu, le chercher sur Google)): ")
        self.epsg_edit = QLineEdit()
        layout.addWidget(self.epsg_label)
        layout.addWidget(self.epsg_edit)
        
        self.centre_site_label = QLabel("Coordonnées du centre du site (longitude, latitude ) : ")
        self.link_label = QLabel('<a href="https://app.dogeo.fr/Projection/#/point-to-coords">Cliquez ici pour trouver les coordonnées du site souhaité</a>')
        self.link_label.setOpenExternalLinks(True)
        self.link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.link_label.setFixedWidth(500)
        self.centre_site_edit = QLineEdit()
        layout.addWidget(self.centre_site_label)
        layout.addWidget(self.link_label)
        layout.addWidget(self.centre_site_edit)
        
        self.rayon_ajoute_label = QLabel("Rayon Ajouté : ")
        self.rayon_ajoute_edit = QLineEdit()
        layout.addWidget(self.rayon_ajoute_label)
        layout.addWidget(self.rayon_ajoute_edit)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok| QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.ok_button = self.buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        layout.addWidget(self.buttons)
        
        self.setLayout(layout)
        self.resize(600, 500)
        
        self.dossier_resultats_edit.textChanged.connect(self.check_inputs)
        self.epsg_edit.textChanged.connect(self.check_inputs)
        self.centre_site_edit.textChanged.connect(self.check_inputs)
        self.rayon_ajoute_edit.textChanged.connect(self.check_inputs)
    
    def select_folder(self, dossier_edit):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if folder:
            dossier_edit.setText(folder)
    
    def check_inputs(self):
        if (self.dossier_resultats_edit.text() and 
            self.epsg_edit.text() and 
            self.centre_site_edit.text() and 
            self.rayon_ajoute_edit.text()):
            self.ok_button.setEnabled(True)
        else:
            self.ok_button.setEnabled(False)
    
    def getParametres(self):
        dossier_resultats = self.dossier_resultats_edit.text()
        EPSG_cible = int(self.epsg_edit.text())
        centre_site_text = self.centre_site_edit.text()
        centre_site = tuple(map(float, re.findall(r'-?\d+\.\d+', centre_site_text)))
        rayon_ajoute = float(self.rayon_ajoute_edit.text())
        return dossier_resultats, EPSG_cible, centre_site, rayon_ajoute

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


"""Ce code sert à extraire le cadastre afin de pouvoir tracer précisément l'emprise 
du projet sans avoir à stocker de couche en local et sans ralentir QGIS"""


#==============================================================================
# Corps du script
#==============================================================================

def PreextractionCadastre():
    param_dialog = ParametresDialog()
    if param_dialog.exec_() == QDialog.Accepted:
        dossier_resultats, EPSG_cible, centre_site, rayon_ajoute = param_dialog.getParametres()
        dossier_resultats.encode("cp1252")
    else: 
        myDlg = QMessageBox()
        myDlg.setText( """Les variables initiales n'ont pas été correctement initialisées.

Veuillez réessayer en inscrivant correctement toutes les variables.""")
        myDlg.exec_()
        return

    #Si le dossier n'existe pas, on le crée
    path_resultats = os.path.join(dossier_resultats, "Resultats_extraction_cadastres")
    #Si le dossier n'existe pas, on le crée
    if not os.path.isdir(path_resultats):
            os.mkdir(path_resultats)
    else :
        reply = QMessageBox()
        reply.setText("""Dossier résultat existant, voulez-vous supprimer le contenu déjà existant ?\n
                        Oui supprimera le dossier existant""")
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reply.setDefaultButton(QMessageBox.No)
        x = reply.exec_()
        if x == QMessageBox.Yes:
            shutil.rmtree(path_resultats)
            os.mkdir(path_resultats)

    #Si le dossier  de travail n'existe pas, on envoie un message d'erreur
    if type(centre_site) is not tuple:
        myDlg = MyDialog()
        myDlg.message="""La variable centre_site n'est pas au bon format. Pour rappel,
        il faut deux chiffres séparées par une virgule. Le tout placé entre parenthèse.
        Le séparateur entre unités et décimal est le "."
        Exemple : (84.5136 ,2352.5448)"""
        myDlg.show()
        myDlg.run()
        return 

    #Si le dossier  de travail n'existe pas, on envoie un message d'erreur
    dossier_travail = os.path.join(dossier_resultats, "Travail_extraction_cadastres")
    #Si le dossier n'existe pas, on le crée
    if not os.path.isdir(dossier_travail):
            os.mkdir(dossier_travail)
    else :
        reply = QMessageBox()
        reply.setText("""Dossier travail existant, voulez-vous supprimer le contenu déjà existant ?\n
                        Oui supprimera le dossier existant""")
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reply.setDefaultButton(QMessageBox.No)
        x = reply.exec_()
        if x == QMessageBox.Yes:
            shutil.rmtree(dossier_travail)
            os.mkdir(dossier_travail)

    #Cas particulier pour le rayon en coordonnées GPS
    EPSG_CRS=QgsCoordinateReferenceSystem("EPSG:%s"%(EPSG_cible))
    if EPSG_CRS.isGeographic()==True:
        rayon_terre= 6378137
        extended_clipBbox = [centre_site[0]-(180.*rayon_ajoute/np.pi)/(rayon_terre*np.cos(centre_site[1]*np.pi/180.)),
                         centre_site[1]-180.*rayon_ajoute/(np.pi*rayon_terre),
                         centre_site[0]+(180.*rayon_ajoute/np.pi)/(rayon_terre*np.cos(centre_site[1]*np.pi/180.)),
                         centre_site[1]+180*rayon_ajoute/(np.pi*rayon_terre)]



    #Creation du polygone étendu
    crs = "EPSG:%s"%(EPSG_cible)  # CRS en dur car dans le fichier c'est le plus commun mais pas renseigné
    layer = QgsVectorLayer("Polygon?crs=" + crs, "Layer", "memory")
    pr=layer.dataProvider()
    layer.startEditing()
    feat = QgsFeature(layer.fields())
    geom = QgsGeometry.fromPolygonXY([[QgsPointXY(extended_clipBbox[0],extended_clipBbox[1]),
                                       QgsPointXY(extended_clipBbox[2],extended_clipBbox[1]),
                                       QgsPointXY(extended_clipBbox[2],extended_clipBbox[3]),
                                       QgsPointXY(extended_clipBbox[0],extended_clipBbox[3])]])
    feat.setGeometry(geom)
    layer.addFeature(feat)
    layer.commitChanges()
    QgsVectorFileWriter.writeAsVectorFormat(layer,os.path.join(path_resultats,"Emprise_etendue.shp"),"utf-8",driverName="ESRI Shapefile")

    #Chargement de la couche de découpe, soit l'emprise du projet étendue
    emprises_etendu = layer.getFeatures() #Nombre de sous domaines dans l'emprise
    nombre_emp_etendu=layer.featureCount()
    if nombre_emp_etendu != 1 :
        myDlg = MyDialog()
        myDlg.message="""Emprises non reliées, attention à la gestion des chiffrages. 
        Pour l'instant un seul polygone par chiffrage est prévu, 
        la concaténation de résultat peut éventuellement se faire à la main."""
        myDlg.show()
        myDlg.run()
        return 
        
    #Récupération des parcelles cadastrales
    #Pour la connexion on a l'identifiant, puis l'adresse (qui contient le mode de récupération)
    #Et enfin la liste des couches recherchées
    HEADERS = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:99.0) Gecko/20100101 Firefox/99.0'}
    url='https://wxs.ign.fr/parcellaire/geoportail/wfs?'
    wanted_list = ['CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle']
    #Boucle sur les couches
    for couche in wanted_list:
        #Début de la construction de l'url
        featurelayer=os.path.join(dossier_travail,str(couche).split(":")[0]+'.shp')
        srs_string="EPSG:"+str(EPSG_cible)
        if EPSG_CRS.isGeographic()==True:
            uri = url+"service=wfs&version=2.0.0&request=GetFeature&srsName=" + \
            srs_string+"&typename="+couche+ \
            "&bbox=%.7f,%.7f,%.7f,%.7f"%(extended_clipBbox[0],extended_clipBbox[1],extended_clipBbox[2],extended_clipBbox[3])+\
            ",epsg:%s"%(EPSG_cible)+"&outputFormat=shape-zip"
        else:
            uri = url+"service=wfs&version=2.0.0&request=GetFeature&srsName=" + \
            srs_string+"&typename="+couche+ \
            "&bbox=%.0f,%.0f,%.0f,%.0f"%(extended_clipBbox[0],extended_clipBbox[1],extended_clipBbox[2],extended_clipBbox[3])+\
            ",epsg:%s"%(EPSG_cible)+"&outputFormat=shape-zip"
        # Fin de la construction de l'url
        # On récupère le dossier sous format zip, on doit donc récupérer puis extraire
        request = requests.get(uri)
        zip = zipfile.ZipFile(io.BytesIO(request.content))
        zip.extractall(dossier_travail)
        # Une fois extrait, on lance l'algorithme de clip par l'emprise étendue
        # On récupère donc seulement les parcelles alentour pour gagner en temps de chargement
        input=os.path.join(dossier_travail,str(couche).split(":")[1]+'.shp')
        result=processing.run("qgis:clip",{"INPUT":input,"OVERLAY":layer,"OUTPUT":"TEMPORARY_OUTPUT"})["OUTPUT"]
        nombre_extrait= result.featureCount() #Récupération du nombre d'entités coupés
        if nombre_extrait: #S'il y a des entités dans la couche shp concernée 
          # On choppe le dataprovider qui sert à ajouter des données
          QgsProject.instance().addMapLayer(result)
          QgsVectorFileWriter.writeAsVectorFormat(result,os.path.join(path_resultats,str(couche).split(":")[1]+"_decoupe.shp"),
                                                  "utf-8",QgsCoordinateReferenceSystem("EPSG:%s"%(EPSG_cible)),
                                                   driverName="ESRI Shapefile")

if __name__ == "__main__":
    PreextractionCadastre()
