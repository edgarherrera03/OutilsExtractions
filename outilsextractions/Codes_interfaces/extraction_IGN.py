# -*- coding: utf-8 -*-
"""
Created on Wed Jun 5 11:23:35 2024

@author: Edgar HERRERA SANSIVIRINI
"""

"""
Cette fonction permet d'extraire les vues cartographiques des différents éléments
nécessaires à l'étude d'un périmètre donné. Le but est de fournir un état initial 
pour l'étude de faisabilité.

"""
#==============================================================================
# Modules à importer : NE PAS TOUCHER
#==============================================================================
from ..Outils import export_word
import os 
import sys
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtWidgets import *
from PyQt5.QtCore import Qt
import requests
import shutil
import numpy as np
from io import BytesIO
import re
from ..Outils import ExtractionPlan, ExtractionPlanOrtho, ExtractionPlanIGN, ExtractionSimplePlanIGN, ExtractionTopographie, ExtractionGeologie, ExtractionCavites, ExtractionPollution, ExtractionInondation, ExtractionInondationSumersionMarine, ExtractionRemonteeNappes, ExtractionCouleesDeBoue, ExtractionZonesHumides, ExtractionNatura2000, ExtractionZNIEFF
#==============================================================================
# Paramètres du script
#==============================================================================

#Classe pour la fonctionnalité "Drag and Drop"
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

#Classe pour renseigner les paramètres 
class ParametresDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Etat intial : extraction faisabilité")
        # Créer un QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.checkall = True

        # Créer un widget de conteneur pour le contenu de la boîte de dialogue
        container_widget = QWidget()
        layout = QVBoxLayout(container_widget)
        
        self.dossier_resultats_label = QLabel("Chemin d'accès au dossier résultats : ")
        self.dossier_resultats_button = QPushButton("Sélectionner un dossier")
        self.dossier_resultats_button.setFixedSize(170, 25)
        self.dossier_resultats_edit = DroppableLineEdit()
        
        self.dossier_resultats_button.clicked.connect(lambda : self.select_folder(self.dossier_resultats_edit))
        
        layout.addWidget(self.dossier_resultats_label)
        layout.addWidget(self.dossier_resultats_edit)
        layout.addWidget(self.dossier_resultats_button)
        
        self.document_word_sortie_label = QLabel("Nom du document word résultat:")
        self.document_word_sortie_edit = QLineEdit()
        
        layout.addWidget(self.document_word_sortie_label)
        layout.addWidget(self.document_word_sortie_edit)
        
        self.centre_site_label = QLabel("""Coordonnées du centre du site (longitude, latitude) : """)
        self.link_label = QLabel('<a href="https://app.dogeo.fr/Projection/#/point-to-coords">Cliquez ici pour trouver les coordonnées du site souhaité</a>')
        self.link_label.setOpenExternalLinks(True)
        self.link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.link_label.setFixedWidth(500)
        self.centre_site_edit = QLineEdit()
        layout.addWidget(self.centre_site_label)
        layout.addWidget(self.link_label)
        layout.addWidget(self.centre_site_edit)
        
        self.epsg_label = QLabel("EPSG (Rentrez le code du système de coordonnées souhaité (si inconnu, le chercher sur Google)) : ")
        self.epsg_edit = QLineEdit()
        layout.addWidget(self.epsg_label)
        layout.addWidget(self.epsg_edit)
        
        self.rayon_ajoute_label = QLabel("Rayon ajouté (en m) : ")
        self.rayon_ajoute_edit = QLineEdit()
        layout.addWidget(self.rayon_ajoute_label)
        layout.addWidget(self.rayon_ajoute_edit)
        
        self.rayon_checkbox = QCheckBox("")

        self.choices_label = QLabel("""Choix des extractions à faire : 
Par défaut les rayons sont les mêmes que celui indiqué précédamment. """)
        layout.addWidget(self.choices_label)
        self.checkboxes = {}
        self.rayon_checkboxes = {}
        
        check_all = QCheckBox("Selectionner tout")
        check_all.stateChanged.connect(self.toggleCheckAll)
        layout.addWidget(check_all)
        
        extractions = ["Topographie", "Geologie", "Cavites", "Pollution", "Inondations",
        "Inondations par sumersion marine", "Remontee des nappes", "Coulees de boue", "Zones humides", "Natura2000",
        "ZNIEFF"]
        for extraction in extractions:
            checkbox = QCheckBox(extraction)

            rayon_container_widget = QWidget()
            rayon_perso_layout = QHBoxLayout()
            rayon_container_widget.setLayout(rayon_perso_layout)
            rayon_checkbox = QCheckBox()
            rayon_checkbox_label = QLabel("Rayon spécifique (en m)")
            rayon_edit = QLineEdit()
            rayon_checkbox.setEnabled(False)
            rayon_checkbox_label.setEnabled(False)
            rayon_edit.setEnabled(False)

            rayon_checkbox.toggled.connect(lambda checked, rc=rayon_checkbox, rl=rayon_checkbox_label, re=rayon_edit: self.toggleRayonSpecifique(rc, rl, re))
            checkbox.toggled.connect(lambda toggleCheck, box=checkbox, widget=rayon_checkbox: self.toogleWidget(box, widget))

            rayon_perso_layout.addWidget(rayon_checkbox)
            rayon_perso_layout.addWidget(rayon_checkbox_label)
            rayon_perso_layout.addWidget(rayon_edit)
            
            layout.addWidget(checkbox)
            layout.addWidget(rayon_container_widget)
            self.checkboxes[extraction] = checkbox
            self.rayon_checkboxes[extraction] = [rayon_checkbox, rayon_edit]

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.confirm_selection)
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
        
        self.dossier_resultats_edit.textChanged.connect(self.check_inputs)
        self.epsg_edit.textChanged.connect(self.check_inputs)
        self.centre_site_edit.textChanged.connect(self.check_inputs)
        self.rayon_ajoute_edit.textChanged.connect(self.check_inputs)
        self.document_word_sortie_edit.textChanged.connect(self.check_inputs)
        
    def toggleCheckAll(self):
        for extraction in self.checkboxes:
            self.checkboxes[extraction].setChecked(self.checkall)
        self.checkall = not self.checkall
    
    def toogleWidget(self, box, widget):
        widget.setEnabled(box.isChecked())

    def toggleRayonSpecifique(self, checkbox, label, line_edit):
        Enable = checkbox.isChecked()
        label.setEnabled(Enable)
        line_edit.setEnabled(Enable)

    def confirm_selection(self):
        self.choices = []
        self.rayon = {}
        for extraction in self.checkboxes:
            if self.checkboxes[extraction].isChecked():
                self.choices.append(extraction)
        for extraction in self.choices:
            if self.rayon_checkboxes[extraction][0].isChecked():
                self.rayon[extraction] = int(self.rayon_checkboxes[extraction][1].text())
            else:
                self.rayon[extraction] = None

        self.accept()
    
    def select_folder(self, dossier_edit):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if folder:
            dossier_edit.setText(folder)
    
    def check_inputs(self):
        if (self.dossier_resultats_edit.text() and 
            self.document_word_sortie_edit.text() and
            self.epsg_edit.text() and 
            self.centre_site_edit.text() and 
            self.rayon_ajoute_edit.text()):
            self.ok_button.setEnabled(True)
        else:
            self.ok_button.setEnabled(False)
        
    def getParametres(self):
        dossier_resultats = self.dossier_resultats_edit.text()
        document_word = self.document_word_sortie_edit.text()
        EPSG = int(self.epsg_edit.text())
        centre_site_text = self.centre_site_edit.text()
        centre_site = tuple(map(float, re.findall(r'-?\d+\.\d+', centre_site_text)))
        rayon_ajoute = float(self.rayon_ajoute_edit.text())
        return dossier_resultats, EPSG, centre_site, rayon_ajoute, self.choices, document_word, self.rayon

#==============================================================================
# Corps du script
#==============================================================================
def calcul_bbox(coordonnees ,rayon_ajoute, EPSG):
    if EPSG.isGeographic(): 
        rayon_terre= 6378137
        delta_longitude = (180.*rayon_ajoute/np.pi)/(rayon_terre*np.cos(coordonnees[1]*np.pi/180.))
        delta_latitude = 180.*rayon_ajoute/(np.pi*rayon_terre)

        extended_clipBbox = [coordonnees[0]- delta_longitude,
                    coordonnees[1]- delta_latitude,
                    coordonnees[0]+ delta_longitude,
                    coordonnees[1]+ delta_latitude]
    else:
        extended_clipBbox = [coordonnees[0]- rayon_ajoute,
                    coordonnees[1]- rayon_ajoute,
                    coordonnees[0]+ rayon_ajoute,
                    coordonnees[1]+ rayon_ajoute]

    return extended_clipBbox

def Faisabilite():
    #Initialisation des valeurs communes à toutes les fonctions 
    width = 1000
    height = 1000
    images_data = []
    
    #Initialisation des variables 
    param_dialog = ParametresDialog()
    if param_dialog.exec_() == QDialog.Accepted:
        dossier_resultats, EPSG, centre_site, rayon_ajoute, choices, document_word, rayons = param_dialog.getParametres()
        dossier_resultats.encode("cp1252")
        document_word = document_word + ".docx"
    else: 
        myDlg = QMessageBox()
        myDlg.setText( """Les variables initiales n'ont pas été correctement initialisées.

Veuillez réessayer en inscrivant correctement toutes les variables.""")
        myDlg.exec_()
        return
    
    path_resultats = os.path.join(dossier_resultats, "Resultats_État_Initial")
    document_word = os.path.join(path_resultats, document_word)
    #Si le dossier n'existe pas, on le crée
    if not os.path.isdir(path_resultats):
        reply = QMessageBox()
        reply.setText("""Dossier résultat inexistant, voulez-vous le créer ? \n
                         "Non" arrêtera le script.""")
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        x = reply.exec_()
        if x == QMessageBox.Yes:
            os.mkdir(path_resultats)
        else:
            return 
    else :
        reply = QMessageBox()
        reply.setText("""Dossier résultat existant, voulez-vous supprimer le contenu déjà existant ?\n
                        "Oui" supprimera le dossier définitivement, attention.""")
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reply.setDefaultButton(QMessageBox.No)
        x = reply.exec_()
        if x == QMessageBox.Yes:
            shutil.rmtree(path_resultats)
            os.mkdir(path_resultats)
    
    #On va creer un dossier pour chaque donnée
    dossier_donnees = os.path.join(path_resultats, "Donnees extraites")
    os.mkdir(dossier_donnees)
    
    dossier_Plan_Generaux = os.path.join(dossier_donnees, "Plans Generaux")
    os.mkdir(dossier_Plan_Generaux)
    
    dossier_zones_humides = os.path.join(dossier_donnees, "Zones Humides")
    dossier_ZNIEFF = os.path.join(dossier_donnees, "ZNEIFF")
    dossier_Natura = os.path.join(dossier_donnees, "Natura2000")
    dossier_Topographie = os.path.join(dossier_donnees, "Topographie")
    dossier_Geologie = os.path.join(dossier_donnees, "Geologie")
    dossier_Cavites = os.path.join(dossier_donnees, "Cavites")
    dossier_Pollution = os.path.join(dossier_donnees, "Pollution")
    dossier_Remontee = os.path.join(dossier_donnees, "Remontee des Nappes")
    dossier_Inondation = os.path.join(dossier_donnees, "Inondations")
    dossier_InondationSumersion = os.path.join(dossier_donnees, "Inondations par sumersion marine")
    dossier_Coulees = os.path.join(dossier_donnees, "Coulees de boue")
    
    #Cas particulier pour le rayon en coordonnées GPS
    EPSG_CRS=QgsCoordinateReferenceSystem("EPSG:%s"%(EPSG))

    #Referenciel de travail pour l'extraction des données
    EPSG_Travail=QgsCoordinateReferenceSystem("EPSG:3857")
    ESPG_Extraction_Plan = QgsCoordinateReferenceSystem("EPSG:4326")

    #Transformation des coordonnées dans le referenciel de travail
    transform = QgsCoordinateTransform(EPSG_CRS, EPSG_Travail, QgsProject.instance())
    point = QgsPointXY(centre_site[0], centre_site[1])
    nouvelles_coord = transform.transform(point)

    extended_clipBbox = calcul_bbox(nouvelles_coord, rayon_ajoute, EPSG_Travail)
                        
    #Tranformation des coordonnées dans le referenciel d'extraction du plan 
    transform = QgsCoordinateTransform(EPSG_CRS, ESPG_Extraction_Plan, QgsProject.instance())
    point = QgsPointXY(centre_site[0], centre_site[1])
    nouvelles_coord_plan = transform.transform(point)
    
    extended_clipBbox_plan = calcul_bbox(nouvelles_coord_plan, rayon_ajoute, ESPG_Extraction_Plan)

    #Creation du polygone étendu
    crs = f"EPSG:{EPSG}" 
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
    
    #On gere le choix d'extractions qu'on souhaite faire 
    functions = {
        "ZNIEFF": [ExtractionZNIEFF, dossier_ZNIEFF],
        "Natura2000": [ExtractionNatura2000, dossier_Natura],
        "Topographie": [ExtractionTopographie, dossier_Topographie],
        "Geologie": [ExtractionGeologie, dossier_Geologie],
        "Cavites": [ExtractionCavites, dossier_Cavites],
        "Pollution": [ExtractionPollution, dossier_Pollution],
        "Remontee des nappes": [ExtractionRemonteeNappes, dossier_Remontee],
        "Inondations": [ExtractionInondation, dossier_Inondation],
        "Inondations par sumersion marine": [ExtractionInondationSumersionMarine, dossier_InondationSumersion],
        "Coulees de boue": [ExtractionCouleesDeBoue, dossier_Coulees],
        "Zones humides": [ExtractionZonesHumides, dossier_zones_humides]
    }
    ExtractionPlan(extended_clipBbox_plan, dossier_Plan_Generaux, width, height, images_data)
    ExtractionPlanOrtho(extended_clipBbox, dossier_Plan_Generaux, width, height, images_data)
    dossier_PlanIGN = ExtractionPlanIGN(extended_clipBbox, path_resultats, width, height, images_data)
    if dossier_PlanIGN:
        for choice in choices:
            if choice in functions:
                os.mkdir(functions[choice][1])
                if rayons[choice] == None:
                    functions[choice][0](extended_clipBbox, functions[choice][1], width, height, images_data, dossier_PlanIGN)
                else:
                    bbox = calcul_bbox(nouvelles_coord, rayons[choice], EPSG_Travail)
                    dossier_nouveau_PlanIGN = ExtractionSimplePlanIGN(bbox, functions[choice][1], width, height)
                    if dossier_nouveau_PlanIGN:
                        functions[choice][0](bbox, functions[choice][1], width, height, images_data, dossier_nouveau_PlanIGN)
                    else:
                        print("Erreur dans la récupération du plan adapté IGN")
            else:
                print(f"Choix invalide : {choice}")
    
    export_word(document_word, images_data)

if __name__ == "__main__":
    Faisabilite()

