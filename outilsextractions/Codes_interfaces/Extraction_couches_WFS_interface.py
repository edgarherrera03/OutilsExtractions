# -*- coding: utf-8 -*-
"""
Created on Wed Apr 27 11:23:35 2022

@author: Sami
"""
#==============================================================================
# Modules à importer : NE PAS TOUCHER
#==============================================================================

import os 
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLineEdit, QFileDialog
import requests, zipfile, io
import shutil
import numpy as np
import re
from ..Outils import extractionUrlCategories, extractionDonneesCategories

#==============================================================================
# Paramètres du script
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

class ParametresDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Paramètres extraction couches WFS")
        
        # Créer un QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

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
        
        self.rayon_ajoute_label = QLabel("Rayon ajouté (en m): ")
        self.rayon_ajoute_edit = QLineEdit()
        layout.addWidget(self.rayon_ajoute_label)
        layout.addWidget(self.rayon_ajoute_edit)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.ok_button = self.buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        layout.addWidget(self.buttons)
    
        # Définir le widget de conteneur comme widget du QScrollArea
        scroll_area.setWidget(container_widget)

        # Créer un layout principal pour la boîte de dialogue et ajouter le QScrollArea
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)
        
        self.resize(650, 500)
        
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
        EPSG = int(self.epsg_edit.text())
        centre_site_text = self.centre_site_edit.text()
        centre_site = tuple(map(float, re.findall(r'-?\d+\.\d+', centre_site_text)))
        rayon_ajoute = float(self.rayon_ajoute_edit.text())
        return dossier_resultats, EPSG, centre_site, rayon_ajoute

class ExtractionDialog(QDialog):
    def __init__(self, extraction_list):
        super().__init__()
        self.setWindowTitle("Types de données à extraire")
        self.selected_extraction = []  
        self.extraction_list = extraction_list
        self.initUI()
        
    def initUI(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container_widget = QWidget()
        layout = QVBoxLayout(container_widget)

        self.checkboxes = []
        for extraction in self.extraction_list.keys():
            checkbox = QCheckBox(extraction.capitalize())
            setattr(self, extraction.lower().replace(" ", "_") + "_checkbox", checkbox)  # Assigner dynamiquement la checkbox comme attribut
            self.checkboxes.append(checkbox)
            layout.addWidget(checkbox)
            checkbox.stateChanged.connect(self.check_inputs)
        
        self.confirm_button = QPushButton("Confirmer")
        self.confirm_button.clicked.connect(self.confirmSelection)
        self.confirm_button.setEnabled(False)
        layout.addWidget(self.confirm_button)
        
        # Définir le widget de conteneur comme widget du QScrollArea
        scroll_area.setWidget(container_widget)

        # Créer un layout principal pour la boîte de dialogue et ajouter le QScrollArea
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)
        
        self.resize(600, 600)
    
    def check_inputs(self):
        if any(checkbox.isChecked() for checkbox in self.checkboxes):
            self.confirm_button.setEnabled(True)
        else:
            self.confirm_button.setEnabled(False)
    
    def confirmSelection(self):
        self.selected_extraction = []
        for attr_name in dir(self):
            if hasattr(getattr(self, attr_name), 'isChecked'):
                checkbox = getattr(self, attr_name)
                if checkbox.isChecked():
                    self.selected_extraction.append(checkbox.text().lower())
        
        self.accept()
    
    def getSelectedExtraction(self):
        return self.selected_extraction

class ChoixDonneesDialog(QDialog):
    def __init__(self, selected_extraction, extraction_list):
        super().__init__()
        self.setWindowTitle("Choix des données")
        self.selected_extraction = selected_extraction
        self.extraction_list = extraction_list
        self.choix = {}
        self.initUI()
    
    def initUI(self):
        self.scroll_content = QVBoxLayout()
        
        for extraction_title in self.selected_extraction:
            label = QLabel(extraction_title.capitalize())
            setattr(self, extraction_title.lower().replace(" ", "_") + "_label", label)
            self.scroll_content.addWidget(label)
            
            self.checkboxes = []
            if self.extraction_list[extraction_title]:
                for name in self.extraction_list[extraction_title]:
                    checkbox = QCheckBox(name)
                    setattr(self, name.lower().replace(" ", "_") + "_checkbox", checkbox)
                    checkbox.stateChanged.connect(self.check_inputs)
                    self.checkboxes.append(checkbox)
                    self.scroll_content.addWidget(checkbox)
            self.choix[extraction_title] = self.checkboxes
        
        scroll_widget = QWidget()
        scroll_widget.setLayout(self.scroll_content)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_widget)
        
        self.confirm_button = QPushButton("Confirmer")
        self.confirm_button.clicked.connect(self.confirmSelection)
        self.confirm_button.setEnabled(False)
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(self.confirm_button)
        self.setLayout(main_layout)
        self.resize(600, 500)
    
    def check_inputs(self):
        any_checked = False

        for i in range(self.scroll_content.count()):
            widget = self.scroll_content.itemAt(i).widget()
            if isinstance(widget, QCheckBox) and widget.isChecked():
                any_checked = True
                break
                
        self.confirm_button.setEnabled(any_checked)
    
    def confirmSelection(self):
        for extraction_title, checkboxes in self.choix.items():
            selected_values = [checkbox.text() for checkbox in checkboxes if checkbox.isChecked()]
            self.choix[extraction_title] = selected_values
        
        self.accept()
    
    def getChoix(self):
        return self.choix

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

def ExtractionCouches():
    donnees_list = extractionDonneesCategories("orthohisto")
    extraction_list = extractionUrlCategories()
    if extraction_list:
        extraction = ExtractionDialog(extraction_list)
        if extraction.exec_():
            selected_extraction = extraction.getSelectedExtraction()
            if selected_extraction:
                donnees_dialog = ChoixDonneesDialog(selected_extraction, extraction_list)
                if donnees_dialog.exec_():
                    selected_choix = donnees_dialog.getChoix()
                else:
                    myDlg = QMessageBox()
                    myDlg.setText("""Aucun type de données n'a été sélectionné.

Veuillez réessayer en selectionnant au moins une catégorie.""")
                    myDlg.exec_()
                    return 
            else: 
                myDlg = QMessageBox()
                myDlg.setText("""Une erreur est survenue lors de l'extraction des types de données. Veuillez réessayer.

Si l'erreur persiste, veuillez consulter le concepteur du code.""")
                myDlg.exec_()
                return  
        else:
            myDlg = QMessageBox()
            myDlg.setText("""Aucune catégorie n'a été sélectionnée.

Veuillez réessayer en selectionnant au moins une catégorie.""")
            myDlg.exec_()
            return  
    else:
        myDlg = QMessageBox()
        myDlg.setText( """Une erreur est survenue dans l'extraction des données, veuillez réessayer.

Si l'erreur persiste, veuillez consulter le concepteur du code.""")
        myDlg.exec_()
        return 
    urls = {}
    wanted_liste = {}

    if selected_choix:
        for choix in selected_choix.keys():
            if selected_choix[choix]:
                donnees_list = extractionDonneesCategories(choix)
                urls[choix] = 'https://wxs.ign.fr/' + choix + '/geoportail/wfs?'
                nom_techniques = []
                for nom in selected_choix[choix]:
                    nom_techniques.append(donnees_list[nom])
                wanted_liste[choix] = nom_techniques
    else: 
        myDlg = QMessageBox()
        myDlg.setText("""Aucun type de données n'a été sélectionné.

Veuillez réessayer en selectionnant au moins une catégorie.""")
        myDlg.exec_()
        return 

    param_dialog = ParametresDialog()
    if param_dialog.exec_() == QDialog.Accepted:
        dossier_resultats, EPSG, centre_site, rayon_ajoute = param_dialog.getParametres()
        dossier_resultats.encode("cp1252")
    else: 
        myDlg = QMessageBox()
        myDlg.setText( """Les variables initiales n'ont pas été correctement initialisées.

Veuillez réessayer en inscrivant correctement toutes les variables.""")
        myDlg.exec_()
        return
        
    path_resultats = os.path.join(dossier_resultats, "Resultats_extraction_couches_WFS")
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

    if type(centre_site) is not tuple:
        myDlg = MyDialog()
        myDlg.message="""La variable centre_site n'est pas au bon format. Pour rappel,
        il faut deux chiffres séparées par une virgule. Le tout placé entre parenthèse.
        Le séparateur entre unités et décimal est le "."
        Exemple : (84.5136 ,2352.5448)"""
        myDlg.show()
        myDlg.run()
        return 

    extended_clipBbox = [centre_site[0]-rayon_ajoute,
                         centre_site[1]-rayon_ajoute,
                         centre_site[0]+rayon_ajoute,
                         centre_site[1]+rayon_ajoute]

    #Cas particulier pour le rayon en coordonnées GPS
    EPSG_CRS=QgsCoordinateReferenceSystem("EPSG:%s"%(EPSG))
    if EPSG_CRS.isGeographic()==True:
        rayon_terre= 6378137
        extended_clipBbox = [centre_site[0]-(180.*rayon_ajoute/np.pi)/(rayon_terre*np.cos(centre_site[1]*np.pi/180.)),
                         centre_site[1]-180.*rayon_ajoute/(np.pi*rayon_terre),
                         centre_site[0]+(180.*rayon_ajoute/np.pi)/(rayon_terre*np.cos(centre_site[1]*np.pi/180.)),
                         centre_site[1]+180*rayon_ajoute/(np.pi*rayon_terre)]



    #Creation du polygone étendu
    crs = "EPSG:%s"%(EPSG)  # CRS en dur car dans le fichier c'est le plus commun mais pas renseigné
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

    liste_base_de_donnees=list(urls.keys())
    for j in liste_base_de_donnees:
        wanted_list= wanted_liste[str(j)]
        url = urls[str(j)]
        for couche in wanted_list:
            featurelayer=os.path.join(path_resultats,str(couche).split(":")[1]+'.shp')
            srs_string="EPSG:"+str(EPSG)
            if EPSG_CRS.isGeographic()==True:
                uri = url+"service=wfs&version=2.0.0&request=GetFeature&srsName=" + \
                      srs_string+"&typename="+couche+ \
                      "&bbox=%.7f,%.7f,%.7f,%.7f"%(extended_clipBbox[0],extended_clipBbox[1],extended_clipBbox[2],extended_clipBbox[3])+\
                      ",epsg:%s"%(EPSG)+"&outputFormat=shape-zip"
            else:
                    uri =  url+"service=wfs&version=2.0.0&request=GetFeature&srsName=" + \
                    srs_string+"&typename="+couche+ \
                    "&bbox=%.0f,%.0f,%.0f,%.0f"%(extended_clipBbox[0],extended_clipBbox[1],extended_clipBbox[2],extended_clipBbox[3])+\
                    ",epsg:%s"%(EPSG)+"&outputFormat=shape-zip"
            print(uri)
            request = requests.get(uri)
            try: 
                zip = zipfile.ZipFile(io.BytesIO(request.content))
                zip.extractall(path_resultats)
            except Exception as e:
                print(f"Erreur dans l'extraction de la couche {couche} : {e}")

if __name__=="__main__":
    ExtractionCouches()
