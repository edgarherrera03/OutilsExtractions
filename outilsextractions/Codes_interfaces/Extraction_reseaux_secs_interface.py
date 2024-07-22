# -*- coding: utf-8 -*-
"""
Created on Wed Apr 27 17:45:43 2022

@author: Sami
"""
"""Ce code sert à extraire les réseaux disponibles dans la base de données
par l'emprise du projet. Il crée aussi un script d'import Mensura qui peut 
être utilisé pour importer automatiquement les résultats.
D'autres types de réseaux peuvent être rajoutés dans la base de données au format .shp"""

#==============================================================================
# Modules à importer : NE PAS TOUCHER
#==============================================================================

import os 
import sys
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtWidgets import *
import processing
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLineEdit, QFileDialog
import shutil
import numpy as np

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
        self.setWindowTitle("Paramètres extraction reseaux")
        layout = QVBoxLayout()
        
        self.base_donnees_label = QLabel("Chemin d'accès à la base de données : ")
        self.base_donnees_button = QPushButton("Sélectionner un dossier")
        self.base_donnees_button.setFixedSize(170, 25)
        self.base_donnees_edit = DroppableLineEdit()
        self.base_donnees_edit.setText("P:\Base_de_donnees_QGIS\Reseaux")
        
        self.base_donnees_button.clicked.connect(lambda : self.select_folder(self.base_donnees_edit))
        
        layout.addWidget(self.base_donnees_label)
        layout.addWidget(self.base_donnees_edit)
        layout.addWidget(self.base_donnees_button)
        
        
        self.dossier_resultats_label = QLabel("Chemin d'accès au dossier résultats : ")
        self.dossier_resultats_button = QPushButton("Sélectionner un dossier")
        self.dossier_resultats_button.setFixedSize(170, 25)
        self.dossier_resultats_edit = DroppableLineEdit()
        
        self.dossier_resultats_button.clicked.connect(lambda : self.select_folder(self.dossier_resultats_edit))
        
        layout.addWidget(self.dossier_resultats_label)
        layout.addWidget(self.dossier_resultats_edit)
        layout.addWidget(self.dossier_resultats_button)
       
        
        self.couche_decoupage_label = QLabel("Chemin vers l'emprise du projet tracée à la main : ")
        self.couche_decoupage_button = QPushButton("Sélectionner un fichier")
        self.couche_decoupage_button.setFixedSize(170, 25)
        self.couche_decoupage_edit = DroppableLineEdit()
        
        self.couche_decoupage_button.clicked.connect(lambda: self.select_file(self.couche_decoupage_edit))
        
        layout.addWidget(self.couche_decoupage_label)
        layout.addWidget(self.couche_decoupage_edit)
        layout.addWidget(self.couche_decoupage_button)
        
        self.epsg_source_label = QLabel("EPSG_source (Rentrer le code du système de coordonnées initial du polygone): ")
        self.epsg_source_edit = QLineEdit()
        layout.addWidget(self.epsg_source_label)
        layout.addWidget(self.epsg_source_edit)
        
        self.epsg_cible_label = QLabel("EPSG_cible (Rentrer le code du système de coordonnées final dans lequel les réseaux seront extraits): ")
        self.epsg_cible_edit = QLineEdit()
        layout.addWidget(self.epsg_cible_label)
        layout.addWidget(self.epsg_cible_edit)
        
        self.rayon_ajoute_label = QLabel("Rayon Ajouté (en m) : ")
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
        
        self.base_donnees_edit.textChanged.connect(self.check_inputs)
        self.dossier_resultats_edit.textChanged.connect(self.check_inputs)
        self.couche_decoupage_edit.textChanged.connect(self.check_inputs)
        self.epsg_source_edit.textChanged.connect(self.check_inputs)
        self.epsg_cible_edit.textChanged.connect(self.check_inputs)
        self.rayon_ajoute_edit.textChanged.connect(self.check_inputs)
        
    def select_folder(self, dossier_edit):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if folder:
            dossier_edit.setText(folder)    
    
    def select_file(self, file_edit):
        file, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier")
        if file:
            file_edit.setText(file)
    
    def check_inputs(self):
        if (self.base_donnees_edit.text() and 
            self.dossier_resultats_edit.text() and
            self.couche_decoupage_edit.text() and
            self.epsg_source_edit.text() and
            self.epsg_cible_edit.text() and 
            self.rayon_ajoute_edit.text()):
            self.ok_button.setEnabled(True)
        else:
            self.ok_button.setEnabled(False)
    
    def getParametres(self):
        base_donnees = self.base_donnees_edit.text()
        dossier_resultats = self.dossier_resultats_edit.text()
        couche_decoupage = self.couche_decoupage_edit.text()
        EPSG_source = int(self.epsg_source_edit.text())
        EPSG_cible = int(self.epsg_cible_edit.text())
        rayon_ajoute = float(self.rayon_ajoute_edit.text())
        return base_donnees, dossier_resultats, couche_decoupage, EPSG_source, EPSG_cible, rayon_ajoute

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

def ExtractionReseaux():
    param_dialog = ParametresDialog()
    if param_dialog.exec_() == QDialog.Accepted:
        base_donnees, dossier_resultats, couche_decoupage, EPSG_source, EPSG_cible, rayon_ajoute = param_dialog.getParametres()
        base_donnees.encode("cp1252")
        dossier_resultats.encode("cp1252")
        couche_decoupage.encode("cp1252")
    else: 
        myDlg = QMessageBox()
        myDlg.setText( """Les variables initiales n'ont pas été correctement initialisées.

Veuillez réessayer en inscrivant correctement toutes les variables.""")
        myDlg.exec_()
        return
    
    path_resultats = os.path.join(dossier_resultats, "Resultats_extraction_reseaux")
    #Si le dossier n'existe pas, on le crée
    if not os.path.isdir(path_resultats):
            os.mkdir(path_resultats)
    else :
        reply = QMessageBox()
        reply.setText("""Dossier résultat existant, voulez-vous supprimer le contenu déjà existant? \n
                         "Oui" supprimera le dossier définitivement""")
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reply.setDefaultButton(QMessageBox.No)
        x = reply.exec_()
        if x == QMessageBox.Yes:
            shutil.rmtree(path_resultats)
            os.mkdir(path_resultats)

    #Si la base de données n'existe pas, message d'erreur et arrêt du script
    if not os.path.isdir(base_donnees):
        myDlg = MyDialog()
        myDlg.message="""Dossier base de  données inexistant, le tracé des réseaux ne peut pas fonctionner. 
        Vérifier que la variable est au bon format et que le chemin est correct """
        myDlg.show()
        myDlg.run()
        return

    #Si le projet est mal défini, message d'erreur et arrêt du script
    if not os.path.exists(couche_decoupage) or couche_decoupage[-3:]!="shp":
        myDlg = MyDialog()
        myDlg.message="""Périmètre de projet non pris en compte:
          soit le fichier n'est pas au format shp, soit la variable 'couche_decoupage' est mal renseignée."""
        myDlg.show()
        myDlg.run()
        return

    #Creation du polygone étendu à partir de l'emprise du projet
    emprise = QgsVectorLayer(couche_decoupage,"Emprise_projet","ogr")
    emprises = emprise.getFeatures() #Nombre de sous domaines dans l'emprise
    nombre_emp=emprise.featureCount()
    if nombre_emp > 1 :
        myDlg = MyDialog()
        myDlg.message="""Emprises non reliées, attention à la gestion des chiffrages. 
        Pour l'instant un seul polygone par chiffrage est prévu, 
        la concaténation de résultat peut éventuellement se faire à la main."""
        myDlg.show()
        myDlg.run()
        return
    for emp in emprises: 
        poly = emp

    rayon_ajoute=float(rayon_ajoute)

    clipBbox_temp = poly.geometry().boundingBox()
    extended_clipBbox = [clipBbox_temp.xMinimum()-rayon_ajoute,
                         clipBbox_temp.yMinimum()-rayon_ajoute,
                         clipBbox_temp.xMaximum()+rayon_ajoute,
                         clipBbox_temp.yMaximum()+rayon_ajoute]
    #Cas particulier pour le rayon en coordonnées GPS
    EPSG_CRS=QgsCoordinateReferenceSystem("EPSG:%s"%(EPSG_source))
    if EPSG_CRS.isGeographic()==True:
        rayon_terre= 6378137
        extended_clipBbox = [clipBbox_temp.xMinimum()-(180.*rayon_ajoute/np.pi)/(rayon_terre*np.cos(((clipBbox_temp.yMinimum()+clipBbox_temp.yMaximum())/2)*np.pi/180.)),
                         clipBbox_temp.yMinimum()-180.*rayon_ajoute/(np.pi*rayon_terre),
                         clipBbox_temp.xMaximum()+(180.*rayon_ajoute/np.pi)/(rayon_terre*np.cos(((clipBbox_temp.yMinimum()+clipBbox_temp.yMaximum())/2)*np.pi/180.)),
                         clipBbox_temp.yMaximum()+180*rayon_ajoute/(np.pi*rayon_terre)]
    print(extended_clipBbox)

    #Creation du polygone étendu
    crs = "EPSG:%s"%(EPSG_source) 
    layer = QgsVectorLayer("Polygon?crs=" + crs, "Layer", "memory")
    pr=layer.dataProvider()
    layer.startEditing()
    feat = QgsFeature(layer.fields())
    geom = QgsGeometry.fromPolygonXY([[QgsPointXY(extended_clipBbox[0],extended_clipBbox[1]),
                                       QgsPointXY(extended_clipBbox[2],extended_clipBbox[1]),
                                       QgsPointXY(extended_clipBbox[2],extended_clipBbox[3]),
                                       QgsPointXY(extended_clipBbox[0],extended_clipBbox[3])]])
    
    # Transformation de la géométrie
    source_crs = QgsCoordinateReferenceSystem(EPSG_source)
    target_crs = QgsCoordinateReferenceSystem(EPSG_cible)
    transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    geom.transform(transform) 
    
    feat.setGeometry(geom)
    layer.addFeature(feat)
    layer.commitChanges()
    
    QgsVectorFileWriter.writeAsVectorFormat(layer,os.path.join(path_resultats,"Emprise_etendue.shp"),"utf-8",QgsCoordinateReferenceSystem("EPSG:%s"%(EPSG_cible)),driverName="ESRI Shapefile")

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

    for subdir, dirs, files in os.walk(base_donnees):
      for file in files:
          chemin_complet = os.path.join(subdir,file)
          if file[-3:]=="shp":
            input=chemin_complet
            result=processing.run("qgis:clip",{"INPUT":input,"OVERLAY":layer,"OUTPUT":"TEMPORARY_OUTPUT"})["OUTPUT"]
            nombre_extrait= result.featureCount() #Récupération du nombre d'entités coupés
            if nombre_extrait: #S'il y a des entités dans la couche shp concernée 
                transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem(EPSG_source), QgsCoordinateReferenceSystem(EPSG_cible), QgsProject.instance())
                for feature in result.getFeatures():
                    geom = feature.geometry()
                    geom.transform(transform)
                    feature.setGeometry(geom)
                # On choppe le dataprovider qui sert à ajouter des données
                result.setName(file[:-4])
                QgsProject.instance().addMapLayer(result)
                QgsVectorFileWriter.writeAsVectorFormat(result,os.path.join(path_resultats,file[:-4]+"_decoupe.shp"),
                                                      "utf-8",QgsCoordinateReferenceSystem("EPSG:%s"%(EPSG_cible)),
                                                      driverName="ESRI Shapefile")

    #==============================================================================
    # Création du script d'import mensura
    #==============================================================================
    #Ouverture du fichier de commandes pour import mensura
    recap = open(os.path.join(path_resultats,"cmd_import.cmd"),"w",encoding="utf-8")
    recap.write("okdlg \n")

    #Impossible avec les images malheureusement, mensura ne prend pas d'argument en commande
    for file in os.listdir(path_resultats):
      extension = file[-12:]
      complete_file = os.path.join(path_resultats, file)
      if extension=="_decoupe.shp":
        recap.write("impshp %s\n"%(complete_file))
      elif extension=="_decoupe.dwg" or extension=="dwg":
        recap.write("impdxf %s\n"%(complete_file))
      elif os.path.isdir(complete_file):
        for filebis in os.listdir(complete_file):
          extensionbis = filebis[-12:]
          complete_filebis = os.path.join(complete_file, filebis)
          if extensionbis=="_decoupe.shp":
            recap.write("impshp %s\n"%(complete_filebis))
          elif extensionbis=="_decoupe.dwg" or extension=="dwg":
            recap.write("impdxf %s\n"%(complete_filebis))
    recap.write("okdlg \n")
    recap.close()
    
if __name__=="__main__":    
    ExtractionReseaux()