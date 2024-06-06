# -*- coding: utf-8 -*-
"""
Created on Fri Apr  1 09:00:41 2022

@author: Sami
"""

"""Ce code sert à découper toutes les couches shapefile présentent dans l'instance
du projet par la couche de découpe d'emprises et la couche de parcelles afin 
d'obtenir les quantités dans deux fichiers Excel"""


#==============================================================================
# Modules à importer : NE PAS TOUCHER
#==============================================================================

import os 
import sys
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtWidgets import *
import processing
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QPushButton, QFileDialog
import shutil
import pandas as pd

#==============================================================================
# Paramètres du script
#==============================================================================

"""Ce code sert à découper toutes les couches shapefile présentent dans l'instance
du projet par la couche de découpe d'emprises et la couche de parcelles afin 
d'obtenir les quantités dans deux fichiers Excel"""

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
        self.setWindowTitle("Paramètres métré rapide")
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container_widget = QWidget()
        self.layout = QVBoxLayout(container_widget)
        
        self.fields_layout = QVBoxLayout()
        self.liste_param_souhaite_csv = []

        self.dossier_resultats_label = QLabel("Chemin d'accès au dossier résultats : ")
        self.dossier_resultats_button = QPushButton("Sélectionner un dossier")
        self.dossier_resultats_button.setFixedSize(170, 25)
        self.dossier_resultats_edit = DroppableLineEdit()
        
        self.dossier_resultats_button.clicked.connect(lambda : self.select_folder(self.dossier_resultats_edit))
        
        self.layout.addWidget(self.dossier_resultats_label)
        self.layout.addWidget(self.dossier_resultats_edit)
        self.layout.addWidget(self.dossier_resultats_button)
        

        self.nom_emprise_label = QLabel("Rentrez le nom de la couche d'emprise du projet : ")
        self.nom_emprise_edit = QLineEdit()
        self.layout.addWidget(self.nom_emprise_label)
        self.layout.addWidget(self.nom_emprise_edit)

        self.nom_parcelles_label = QLabel("Rentrez le nom de la couche de parcelles (ou autre couche de découpe) qui est chargée dans le projet : ")
        self.nom_parcelles_edit = QLineEdit()
        self.layout.addWidget(self.nom_parcelles_label)
        self.layout.addWidget(self.nom_parcelles_edit)

        self.utilisation_parcelles_label = QLabel("""
Utilisation_parcelles choisit le mode d'utilisation du script
Mettre à 0 si c'est une couche de découpe qui ne possède pas d'attribut pour identifier les parcelles 
qui découpent.
Mettre à 1 si les couches ont identifiants renseignés dans "identification_champ"
Mettre à 2 si vous voulez lier une couche shapefile avec un fichier csv qui sera renseigné dans la suite:""")
        self.layout.addWidget(self.utilisation_parcelles_label)
        self.utilisation_parcelles = None

        self.utilisation_parcelles_group = QButtonGroup(self)
        self.utilisation_parcelles_group.setExclusive(True)  # Only one checkbox can be checked at a time

        self.utilisation_parcelles_checkbox_0 = QCheckBox("0")
        self.utilisation_parcelles_checkbox_1 = QCheckBox("1")
        self.utilisation_parcelles_checkbox_2 = QCheckBox("2")

        self.utilisation_parcelles_group.addButton(self.utilisation_parcelles_checkbox_0)
        self.utilisation_parcelles_group.addButton(self.utilisation_parcelles_checkbox_1)
        self.utilisation_parcelles_group.addButton(self.utilisation_parcelles_checkbox_2)

        self.utilisation_parcelles_checkbox_0.toggled.connect(lambda: self.toggle_fields(0))
        self.utilisation_parcelles_checkbox_1.toggled.connect(lambda: self.toggle_fields(1))
        self.utilisation_parcelles_checkbox_2.toggled.connect(lambda: self.toggle_fields(2))
        
        self.utilisation_parcelles_checkbox_0.stateChanged.connect(self.update_utilisation_parcelles)
        self.utilisation_parcelles_checkbox_1.stateChanged.connect(self.update_utilisation_parcelles)
        self.utilisation_parcelles_checkbox_2.stateChanged.connect(self.update_utilisation_parcelles)
        
        self.layout.addWidget(self.utilisation_parcelles_checkbox_0)
        self.layout.addWidget(self.utilisation_parcelles_checkbox_1)
        self.layout.addWidget(self.utilisation_parcelles_checkbox_2)
        
        
        self.identification_champ_label = QLabel("Champ de la table d'attributs contenant l'\"adresse\" unique de la parcelle en shp  : ")
        self.identification_champ_edit = QLineEdit()
        self.layout.addWidget(self.identification_champ_label)
        self.layout.addWidget(self.identification_champ_edit)

        self.chemin_csv_label = QLabel("Chemin vers la table du fichier csv qui sera relié à la couche shapefile : ")
        self.chemin_csv_button = QPushButton("Sélectionner un fichier")
        self.chemin_csv_button.setFixedSize(170, 25)
        self.chemin_csv_edit = DroppableLineEdit()
        
        self.chemin_csv_button.clicked.connect(lambda: self.select_file(self.chemin_csv_edit))
        
        self.layout.addWidget(self.chemin_csv_label)
        self.layout.addWidget(self.chemin_csv_edit)
        self.layout.addWidget(self.chemin_csv_button)

        self.separateurchamp_label = QLabel("""
Précisez le sépateur du fichier : en général soit une "," soit un ";"
Pour le savoir ouvrir le fichier avec un éditeur texte et regarder le caractère
qui sépare les différents champs.""")
        self.separateurchamp_edit = QLineEdit()
        self.layout.addWidget(self.separateurchamp_label)
        self.layout.addWidget(self.separateurchamp_edit)

        self.champ_a_lier_shp_label = QLabel("Rentrez le nom du champ dans la couche shapefile : ")
        self.champ_a_lier_shp_edit = QLineEdit()
        self.layout.addWidget(self.champ_a_lier_shp_label)
        self.layout.addWidget(self.champ_a_lier_shp_edit)

        self.champ_a_lier_csv_label = QLabel("Rentrez le nom du champ dans la table csv : ")
        self.champ_a_lier_csv_edit = QLineEdit()
        self.layout.addWidget(self.champ_a_lier_csv_label)
        self.layout.addWidget(self.champ_a_lier_csv_edit)

        self.nom_projet_csv_label = QLabel("Nom du projet avec lequel le fichier csv sera ajoutée au projet : ")
        self.nom_projet_csv_edit = QLineEdit()
        self.layout.addWidget(self.nom_projet_csv_label)
        self.layout.addWidget(self.nom_projet_csv_edit)

        self.liste_param_souhaite_csv_label = QLabel("""Rentrez la liste des champs de la table csv (nom des colonnes) qui apparaîtront 
dans le récapitulatif des parcelles : """)
        self.layout.addWidget(self.liste_param_souhaite_csv_label)

        self.add_field_button = QPushButton("Ajouter une colonne")
        self.add_field_button.setFixedSize(150, 30)
        self.add_field_button.clicked.connect(self.add_field)
        self.fields_layout.addWidget(self.add_field_button)
        self.layout.addLayout(self.fields_layout)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.ok_button = self.buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        

        scroll_area.setWidget(container_widget)

        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(self.buttons)
        self.setLayout(main_layout)

        self.resize(700, 600)

        self.dossier_resultats_edit.textChanged.connect(self.check_inputs)
        self.nom_emprise_edit.textChanged.connect(self.check_inputs)
        self.nom_parcelles_edit.textChanged.connect(self.check_inputs)
        self.identification_champ_edit.textChanged.connect(self.check_inputs)
        self.chemin_csv_edit.textChanged.connect(self.check_inputs)
        self.separateurchamp_edit.textChanged.connect(self.check_inputs)
        self.champ_a_lier_shp_edit.textChanged.connect(self.check_inputs)
        self.champ_a_lier_csv_edit.textChanged.connect(self.check_inputs)
        self.nom_projet_csv_edit.textChanged.connect(self.check_inputs)
        self.toggle_fields(0)
        
    def toggle_fields(self, mode):
        fields_to_toggle = [
            self.identification_champ_edit, self.identification_champ_label,
            self.chemin_csv_edit, self.chemin_csv_button, self.chemin_csv_label,
            self.separateurchamp_edit, self.separateurchamp_label,
            self.champ_a_lier_shp_edit, self.champ_a_lier_shp_label,
            self.champ_a_lier_csv_edit, self.champ_a_lier_csv_label,
            self.nom_projet_csv_edit, self.nom_projet_csv_label,
            self.liste_param_souhaite_csv_label, self.add_field_button
        ]

        # Disable all fields first
        for widget in fields_to_toggle:
            widget.setEnabled(False)

        if mode == 1:
            self.identification_champ_edit.setEnabled(True)
            self.identification_champ_label.setEnabled(True)
        elif mode == 2:
            for widget in fields_to_toggle:
                widget.setEnabled(True)
                
        self.check_inputs()

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

    def select_folder(self, dossier_edit):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if folder:
            dossier_edit.setText(folder)

    def select_file(self, file_edit):
        file, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier")
        if file:
            file_edit.setText(file)
    
    def update_utilisation_parcelles(self):
        # Récupérer l'état des checkboxes
        option_0_checked = self.utilisation_parcelles_checkbox_0.isChecked()
        option_1_checked = self.utilisation_parcelles_checkbox_1.isChecked()
        option_2_checked = self.utilisation_parcelles_checkbox_2.isChecked()

        # Déterminer la valeur de utilisation_parcelles en fonction de l'option cochée
        if option_0_checked:
            self.utilisation_parcelles = 0
        elif option_1_checked:
            self.utilisation_parcelles = 1
        elif option_2_checked:
            self.utilisation_parcelles = 2
        else:
            self.utilisation_parcelles = None

        # Mettre à jour les champs et vérifier les entrées
        self.check_inputs()
    
    def check_inputs(self):
        # Vérification des champs de base (dossier, nom emprise, etc.)
        base_fields_filled = (
            self.dossier_resultats_edit.text() and 
            self.nom_emprise_edit.text() and
            self.nom_parcelles_edit.text()
        )

        other_fields = (self.identification_champ_edit.text() and
            self.chemin_csv_edit.text() and
            self.separateurchamp_edit.text() and
            self.champ_a_lier_shp_edit.text() and
            self.champ_a_lier_csv_edit.text() and
            self.nom_projet_csv_edit.text())

        # Vérification si l'option 0 est sélectionnée
        option_0_selected = self.utilisation_parcelles_checkbox_0.isChecked()

        # Vérification si l'option 1 est sélectionnée
        option_1_selected = self.utilisation_parcelles_checkbox_1.isChecked()

        # Logique pour activer ou désactiver le bouton "Ok" en fonction des conditions
        if option_0_selected:
            # L'option 0 est sélectionnée, seuls les champs de base sont nécessaires
            all_fields_filled = bool(base_fields_filled)
        elif option_1_selected:
            # L'option 1 est sélectionnée, les champs de base et le champ d'identification sont nécessaires
            all_fields_filled = bool(base_fields_filled and self.identification_champ_edit.text())
        else:
            # Les autres options, tous les champs sont nécessaires
            # Vérification des champs supplémentaires (liste des champs de la table CSV)
            additional_fields_filled = True
            for i in range(self.fields_layout.count()):
                field_layout = self.fields_layout.itemAt(i).layout()
                if field_layout:
                    text_field = field_layout.itemAt(0).widget()
                    additional_fields_filled =bool(additional_fields_filled and text_field.text())
            all_fields_filled = bool(base_fields_filled and additional_fields_filled and other_fields)

        self.ok_button.setEnabled(all_fields_filled)

    def getParametres(self):
        dossier_resultats = self.dossier_resultats_edit.text()
        nom_emprise = self.nom_emprise_edit.text()
        nom_parcelles = self.nom_parcelles_edit.text()
        utilisation_parcelles = self.utilisation_parcelles
        identification_champ = self.identification_champ_edit.text()
        chemin_csv = self.chemin_csv_edit.text()
        separateurchamp = self.separateurchamp_edit.text()
        champ_a_lier_shp = self.champ_a_lier_shp_edit.text()
        champ_a_lier_csv = self.champ_a_lier_csv_edit.text()
        nom_projet_csv = self.nom_projet_csv_edit.text()
        
        #Ajout des différentes colonnes
        for i in range(self.fields_layout.count()):
            field_layout = self.fields_layout.itemAt(i).layout()
            if field_layout:
                text_field = field_layout.itemAt(0).widget()
                self.liste_param_souhaite_csv.append(text_field.text())

        return (
            dossier_resultats, nom_emprise, nom_parcelles, utilisation_parcelles,
            identification_champ, chemin_csv, separateurchamp, champ_a_lier_shp,
            champ_a_lier_csv, nom_projet_csv, self.liste_param_souhaite_csv
        )    

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

def Metre():
    EPSG_cible = QgsProject.instance().crs() #Lambert-93
    EPSG_source = QgsProject.instance().crs()
    
    param_dialog = ParametresDialog()
    if param_dialog.exec_() == QDialog.Accepted:
        dossier_resultats, nom_emprise, nom_parcelles, utilisation_parcelles, identification_champ, chemin_csv, separateurchamp, champ_a_lier_shp, champ_a_lier_csv, nom_projet_csv, liste_param_souhaite_csv = param_dialog.getParametres()
        dossier_resultats.encode("cp1252")
        chemin_csv.encode('cp1252')
    else: 
        myDlg = QMessageBox()
        myDlg.setText( """Les variables initiales n'ont pas été correctement initialisées.

Veuillez réessayer en inscrivant correctement toutes les variables.""")
        myDlg.exec_()
        return
    
        
    reply = QMessageBox()
    reply.setText("""Attention, le script fonctionne avec toutes les couches dans l'interface
                   Avez-vous nettoyé les couches inutiles ?
                   Avec-vous vérifié le nom des couches pour qu'elles soient cohérentes
                   avec les paramètres du script ?
                   Appuyer sur 'Non' empêchera l'exécution du script pour vous permettre
                   de faire le nettoyage. Relancez le script après.""")
    reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    reply.setDefaultButton(QMessageBox.No)
    x = reply.exec_()
    if x == QMessageBox.No:
        return 
        
    #Si le projet est mal défini, message d'erreur et arrêt du script
    if not QgsProject.instance().mapLayersByName(nom_parcelles):
        myDlg = MyDialog()
        myDlg.message="""Le nom du paramètres de couche de parcelles est mal renseigné et ne se trouve pas dans le projet.
                         Vérifiez la valeur de la variable."""
        myDlg.show()
        myDlg.run()
        return 

    #Si le projet est mal défini, message d'erreur et arrêt du script
    if not QgsProject.instance().mapLayersByName(nom_emprise):
        myDlg = MyDialog()
        myDlg.message="""Le nom du paramètres de couche d'emprise est mal renseigné
                         et ne se trouve pas dans le projet.
                         Vérifiez la valeur de la variable."""
        myDlg.show()
        myDlg.run()
        return 


    couche_parcelle = QgsProject.instance().mapLayersByName(nom_parcelles)[0]
    emprise = QgsProject.instance().mapLayersByName(nom_emprise)[0]

    path_resultats = os.path.join(dossier_resultats, "Resultats_metre_rapide")
    #Si le dossier n'existe pas, on le crée
    if not os.path.isdir(path_resultats):
            os.mkdir(path_resultats)
    else :
        reply = QMessageBox()
        reply.setText("""Dossier résultat déjà existant.
                         Pour ne pas mélanger les couches, il faut un dossier vierge.
                         Le dossier va donc être vidé.
                         Si vous voulez d'abord sauvegarder le contenu actuel, appuyez sur 'Non'.
                         Puis relancez le script.""")
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reply.setDefaultButton(QMessageBox.No)
        x = reply.exec_()
        if x == QMessageBox.Yes:
            shutil.rmtree(path_resultats)
            os.mkdir(path_resultats)

    #Vérification des champs des couches
    champ_couche_parcelle=[]
    for field in list(couche_parcelle.fields()):
        champ_couche_parcelle.append(QgsField.name(field))

    if (utilisation_parcelles == 1) and (identification_champ not in champ_couche_parcelle):
        myDlg = MyDialog()
        myDlg.message="""Le champ %s ne se trouve pas dans les champs d'attribut de la couche choisie pour le découpage.
                         Choisir un champ existant dans la table d'attributs ou le créer, puis relancer le script"""%(identification_champ)
        myDlg.show()
        myDlg.run()

    if (utilisation_parcelles >= 2) and ((identification_champ not in champ_couche_parcelle) \
        or (champ_a_lier_shp not in champ_couche_parcelle)):
        print(champ_couche_parcelle)
        if identification_champ not in champ_couche_parcelle:
            erreur=identification_champ
        else:
            erreur = champ_a_lier_shp
        myDlg = MyDialog()
        myDlg.message="""Le champ %s ne se trouve pas dans les champs d'attribut de la couche choisie pour le découpage.
                         Choisir un champ existant dans la table d'attributs ou le créer, puis relancer le script"""%(erreur)
        myDlg.show()
        myDlg.run()
        return 



    if (utilisation_parcelles >= 2) and ((not os.path.isfile(chemin_csv)) \
        or (chemin_csv[-3:]!="csv")):
        myDlg = MyDialog()
        myDlg.message="""Le fichier csv est soit mal renseigné (inexistant ou avec une erreur dans le chemin d'accès, soit il n'est pas au format csv.
                         Vérifiez le chemin d'accès ou convertissez le au format csv."""
        myDlg.show()
        myDlg.run()
        return 

    #Test fichier csv
    if (utilisation_parcelles >= 2):
        liste_param_souhaite_csv=list(liste_param_souhaite_csv)
        data_set=pd.read_csv(chemin_csv, sep=separateurchamp, dtype=object, encoding="utf-8")

    if (utilisation_parcelles >= 2):
        liste_verif_csv =list(data_set.columns)
        if (champ_a_lier_csv not in liste_verif_csv) :
                    myDlg = MyDialog()
                    myDlg.message="""Le champ %s ne se trouve pas dans les champs du fichier csv.
                         Changer la table csv à lire ou modifier le nom du champ, puis relancer le script"""%(champ_a_lier_csv)
                    myDlg.show()
                    myDlg.run()
                    return 
        else:
            for champ in liste_param_souhaite_csv:
                if champ not in liste_verif_csv:
                    myDlg = MyDialog()
                    myDlg.message="""Le champ %s ne se trouve pas dans les champs du fichier csv.
                         Changer la table csv à lire ou modifier le nom du champ, puis relancer le script"""%(champ)
                    myDlg.show()
                    myDlg.run()
                    return 

    #Creation du polygone étendu à partir de l'emprise du projet
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


    somme_aire=dict()
    somme_longueur=dict()
    nombre_extrait=dict()
    #pub pour public
    #Rempli plus tard une fois qu'on a accès aux parcelles
    somme_aire_pub=dict()
    somme_longueur_pub=dict()
    nombre_extrait_pub=dict()

    #Ouverture du fichier récapitulatif qui contiendra les mesures
    recap = open(path_resultats + "\\Recap.csv","w",encoding="utf-8")
    recap.write(("Emprise projet;Périmètre;Aire \n"))

    #Boucle sur les emprises
    for emp in emprise.getFeatures(): 
        area_calc = QgsDistanceArea()
        if emprise.crs().isGeographic()==True:
          area_calc.setEllipsoid('WGS84') #Peut-être une approximation pour l'ellipsoide mais fera le boulot en faisabilité
        area_calc.willUseEllipsoid()
        area = area_calc.measureArea(emp.geometry())
        id = emp.id()
        perimetre_total = area_calc.measureLength(emp.geometry())
        aire_total = area_calc.measureArea(emp.geometry())
        recap.write("%d;%f;%f\n"%(id+1,perimetre_total,aire_total))#On écrit dans le fichier récapitulatif
        
    recap.write("\n")
    recap.write("Fichiers;Somme_aire;Somme_longueur;Unites\n")
    recap.close()

    couches = QgsProject.instance().mapLayers()
    for couche_id, couche in couches.items():
        if couche.name()!=nom_emprise and couche.type()==QgsMapLayer.VectorLayer:
            input=couche
            print (couche.type())
            print(couche)
            if couche.name().find(":") != (-1):
                couche_name=str(couche.name()).split(":")[1]+"_decoupe"
            else:
                couche_name=couche.name()+"_decoupe"
            for polygonss in emprise.getFeatures():
                # Parcours des entités de la couche de découpe
                id = polygonss.id()
                #Si jamais on veut plutôt extraire par location
                #Plusieurs options : dedans, intersection, exclu, etc.
                #result=processing.run("qgis:extractbylocation",{"INPUT":input,"PREDICATE":6,"INTERSECT":couche_decoupage,"OUTPUT":"TEMPORARY_OUTPUT"})["OUTPUT"]*
                # On coupe
                result=processing.run("qgis:clip",{"INPUT":input,"OVERLAY":emprise,"OUTPUT":"TEMPORARY_OUTPUT"})["OUTPUT"]
                nombre_extrait[couche_name]= result.featureCount() #Récupération du nombre d'entités coupés
                if nombre_extrait[couche_name]: #S'il y a des entités dans la couche shp concernée 
                    #Initialisation des entités à 0
                    somme_aire[couche_name]=0
                    somme_longueur[couche_name]=0
                    # On récupère le dataprovider qui sert à ajouter des données
                    ajout_donnees = result.dataProvider()
                    #On ajoute les champs aire et longueurs à la table d'attributs
                    code_attribut_aire = len(result.fields())
                    champ_aire = "Aire"
                    while champ_aire in result.fields():
                        champ_aire = champ_aire + "1"
                    ajout_donnees.addAttributes([QgsField(champ_aire,QVariant.Double)]) # Peut s'optimiser et créer la liste des deux champs d'un coup
                    result.updateFields()
                    code_attribut_longueur = len(result.fields()) # Après ajout aire
                    champ_long = "Longueur"
                    while champ_long in result.fields():
                        champ_long = champ_aire + "1"
                    ajout_donnees.addAttributes([QgsField(champ_long,QVariant.Double)])
                    result.updateFields()
                    result.commitChanges()
                    formes = result.getFeatures()
                    for f in formes:
                        id = f.id()
                        dist_calc = QgsDistanceArea()
                        if EPSG_cible.isGeographic()==True:
                            dist_calc.setEllipsoid('WGS84')
                        dist_calc.willUseEllipsoid()
                        aire = dist_calc.measureArea(f.geometry())
                        somme_aire[couche_name]+=aire
                        att_aire = {code_attribut_aire:aire}
                        ajout_donnees.changeAttributeValues({id:att_aire})
                        longueur = dist_calc.measureLength(f.geometry())
                        somme_longueur[couche_name]+=longueur
                        att_long = {code_attribut_longueur:longueur}
                        ajout_donnees.changeAttributeValues({id:att_long})
                    result.commitChanges()
                    recap = open(path_resultats +"\\Recap.csv","a",encoding="utf-8")
                    recap.write("%s;%f;%f;%f\n"%(couche_name,\
                                                somme_aire[couche_name],\
                                                somme_longueur[couche_name],\
                                                nombre_extrait[couche_name]))
                    recap.close()
                    lay=QgsProject.instance().addMapLayer(result)
                    lay.setName(couche_name)
                    QgsVectorFileWriter.writeAsVectorFormat(lay,os.path.join(path_resultats,couche_name+".shp"),
                    "utf-8",QgsCoordinateReferenceSystem("EPSG:%s"%(EPSG_cible)),driverName="ESRI Shapefile")

    # On récupère les fichiers qui ont été extraits et donc qui sont dans l'emprise du projet
    liste_fichiers = os.listdir(path_resultats)
    set_name=set()
    for file in liste_fichiers :
        file=file.upper()
        if file[-3:]!="CSV" and file.split("_DECOUPE")[0]!=nom_parcelles.upper(): #Pas les fichiers csv déjà écrits, ni le fichier parcelle (on écrit dessus)
          set_name.add(file[:-4])

    #Nom  du fichier ouvert pour lisibilité, on écrit dans le même fichier
    recap_parc = open(os.path.join(path_resultats,"Recap_parcelle.csv"),"a",encoding="utf-8")
    recap_parc.write("\n")
    recap_parc.write("Décomposition par parcelles \n")
    recap_parc.write("Parcelle;")
    if utilisation_parcelles>=2:
        recap_parc.write(champ_a_lier_shp+";")
        for i in liste_param_souhaite_csv:
            recap_parc.write(i+";")
    recap_parc.write("Aire_Parcelle;")
    liste_name=list(set_name)
    liste_name.sort()
    for name in liste_name:
        recap_parc.write(name+";")
    #recap_parc.seek(-1, os.SEEK_END)
    #recap_parc.truncate()
    recap_parc.write("\n")

    #Chargement couche parcelles
    if(QgsProject.instance().mapLayersByName(nom_parcelles+"_decoupe")==[]):
        myDlg = MyDialog()
        myDlg.message="""L'emprise n'est pas superposée aux couches à métrer. 
        Le script ne peut donc rien découper selon l'emprise. Vérifiez vos systèmes de coordonnées.
        Du projet, et des couches."""
        myDlg.show()
        myDlg.run()
        recap_parc.close()
        return 

    couche_parcelle=QgsProject.instance().mapLayersByName(nom_parcelles+"_decoupe")[0]
    parcelles= couche_parcelle.getFeatures()

    # IMPORTER CSV
    if utilisation_parcelles>=2:
        liste_parc_id=[]
        for parcelle in parcelles :
            liste_parc_id.append(parcelle[champ_a_lier_shp])
        parcelles=None
        mask = data_set[champ_a_lier_csv].apply(lambda x: any(item for item in liste_parc_id if item in x))
        data_set_bis = data_set[mask]
        data_set_bis.to_csv(os.path.join(path_resultats,nom_projet_csv+"_extraites.csv"), sep=separateurchamp, encoding="utf-8")
        
        table_attribut = QgsVectorLayer(os.path.join(path_resultats, nom_projet_csv+"_extraites.csv"), nom_projet_csv, 'ogr')
        table_attribut.setProviderEncoding("UTF-8")
        QgsProject.instance().addMapLayer(table_attribut)
        
        myJoin = QgsVectorLayerJoinInfo()
        myJoin.setJoinFieldName(champ_a_lier_csv)
        myJoin.setTargetFieldName(champ_a_lier_shp)
        myJoin.setJoinLayerId(table_attribut.id())
        myJoin.setUsingMemoryCache(True)
        myJoin.setJoinLayer(table_attribut)
        couche_parcelle.addJoin(myJoin) 
        couche_parcelle.dataProvider().forceReload()
        parcelles= couche_parcelle.getFeatures()

    #parc pour parcelle
    somme_aire_parc=dict()
    somme_longueur_parc=dict()
    nombre_extrait_parc=dict()
    liste_files=os.listdir(path_resultats)
    liste_files.sort
    for i in liste_files:
        dossier_concat=os.path.join(path_resultats,i)
        if (dossier_concat[-3:]=="shp" or dossier_concat[-3:]=="SHP") and (i.split("_decoupe")[0]!=nom_parcelles):
            somme_aire_pub["%s"%(i[:-4])]=0
            somme_longueur_pub["%s"%(i[:-4])]=0
            nombre_extrait_pub["%s"%(i[:-4])]=0

    for parcelle in parcelles :
        couche_parcelle.select(parcelle.id())
        if not os.path.isdir(os.path.join(path_resultats,"Temp")):
            dossier_temp=os.path.join(path_resultats,"Temp")
            os.mkdir(dossier_temp)
        if utilisation_parcelles>0:
            parcelle_id=parcelle[identification_champ]
        else: 
            parcelle_id=str(parcelle.id())
        parcelle_temp_file=os.path.join(dossier_temp,"parcelle_temp_"+parcelle_id+".shp")
        somme_aire_parc["%s"%(parcelle_id)]=dict()
        somme_longueur_parc["%s"%(parcelle_id)]=dict()
        nombre_extrait_parc["%s"%(parcelle_id)]=dict()
        QgsVectorFileWriter.writeAsVectorFormat(couche_parcelle,parcelle_temp_file,fileEncoding="utf-8",driverName="ESRI Shapefile",onlySelected=True)
        print("Parcelle_id : %d"%(parcelle.id()))
        couche_parcelle.deselect(parcelle.id())
        recap_parc.write("%s;"%(parcelle_id))
        if utilisation_parcelles>=2:
            recap_parc.write("%s;"%(parcelle[champ_a_lier_shp]))
            for i in liste_param_souhaite_csv:
                recap_parc.write("%s;"%(parcelle[nom_projet_csv+"_"+i]))
        #aire parcelle
        area_calc = QgsDistanceArea()
        if EPSG_cible.isGeographic()==True:
          area_calc.setEllipsoid('WGS84') #Peut-être une approximation pour l'ellipsoide mais fera le boulot en faisabilité
        area_calc.willUseEllipsoid()
        area = area_calc.measureArea(parcelle.geometry())
        recap_parc.write("%s;"%(area))
        liste_files=os.listdir(path_resultats)
        liste_files.sort
        for i in liste_files:
            dossier_concat=os.path.join(path_resultats,i)
            if (dossier_concat[-3:]=="shp" or dossier_concat[-3:]=="SHP") and (i.split("_decoupe")[0]!=nom_parcelles):
                input=dossier_concat
                result=processing.run("qgis:clip",{"INPUT":input,"OVERLAY":parcelle_temp_file,"OUTPUT":"TEMPORARY_OUTPUT"})["OUTPUT"]
                nombre_extrait_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]= result.featureCount()
                if nombre_extrait_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]:
                    somme_aire_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]=0
                    somme_longueur_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]=0
                    ajout_donnees = result.dataProvider()
                    code_attribut_aire = len(result.fields())
                    ajout_donnees.addAttributes([QgsField("Aire",QVariant.Double)])
                    result.updateFields()
                    code_attribut_longueur = len(result.fields())+1 # Après ajout aire
                    ajout_donnees.addAttributes([QgsField("Longueur",QVariant.Double)])
                    result.updateFields()
                    formes = result.getFeatures()
                    for f in formes:
                        id = f.id()
                        dist_calc = QgsDistanceArea()
                        if EPSG_cible.isGeographic()==True:
                            dist_calc.setEllipsoid('WGS84')
                        dist_calc.willUseEllipsoid()
                        aire = dist_calc.measureArea(f.geometry())
                        longueur = dist_calc.measureLength(f.geometry())
                        somme_aire_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]+=aire
                        attribut_aire = {code_attribut_aire:aire}
                        #ajout_donnees.changeAttributeValues({id:attribut_aire})
                        somme_longueur_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]+=longueur
                        att_long = {code_attribut_longueur:longueur}
                        #ajout_donnees.changeAttributeValues({id:att_long})
                        result.commitChanges()
                    #Pour le public on somme le privé temporairement dans la variable
                    #Une fois toutes les parcelles parcourues on fera emprise-somme des parcelles
                    nombre_extrait_pub["%s"%(i[:-4])]+=nombre_extrait_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]
                    somme_longueur_pub["%s"%(i[:-4])]+=somme_longueur_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]
                    somme_aire_pub["%s"%(i[:-4])]+=somme_aire_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]
                    if somme_aire_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]<=0 and somme_longueur_parc["%s"%(parcelle_id)]["%s"%(i[:-4])] <=0:
                        recap_parc.write("%f;"%(nombre_extrait_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]))
                    elif somme_aire_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]<=0:
                        recap_parc.write("%f;"%(somme_longueur_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]))
                    else:
                        recap_parc.write("%f;"%(somme_aire_parc["%s"%(parcelle_id)]["%s"%(i[:-4])]))
                else:
                    recap_parc.write(";")
        recap_parc.write("\n")

    recap_parc.write("Public;;")
    if utilisation_parcelles>=2:
        recap_parc.write(";")
        for i in range(0, len(liste_param_souhaite_csv)):
            recap_parc.write(";")

    #On parcourt un dictionnaire au hasard, toutes les clés sont les mêmes
    for keys in somme_longueur_pub:
        if keys.find(nom_parcelles)<0: #On ne traite pas cette valeur
            #Cas particuliers si toute la donnée est sur domain public
            if nombre_extrait_pub[keys]==0:
                if somme_aire[keys]<=0:
                    recap_parc.write("%f;"%(somme_longueur[keys]))
                else:
                    recap_parc.write("%f;"%(somme_aire[keys]))
            else:
                if (somme_aire_pub[keys]<=0 and somme_longueur_pub[keys]<=0):
                    recap_parc.write("%d;"%(nombre_extrait[keys]-nombre_extrait_pub[keys]))
                elif(somme_aire_pub[keys]<=0):
                    recap_parc.write("%f;"%(somme_longueur[keys]-somme_longueur_pub[keys]))
                else:
                    recap_parc.write("%f;"%(somme_aire[keys]-somme_aire_pub[keys]))
    recap_parc.write("\n")
    recap_parc.close()
    couche_parcelle= None
    #Remplacement "." par ","

    with open(path_resultats +"\\Recap.csv","r") as file :
      filedata = file.read()
    with open(path_resultats +"\\Recap.csv","w",encoding="ANSI") as file:
      file.write(filedata.replace(".",","))
      
    with open(path_resultats +"\\Recap_parcelle.csv","r") as file :
      filedata = file.read()
    with open(path_resultats +"\\Recap_parcelle.csv","w",encoding="ANSI") as file:
      file.write(filedata.replace(".",","))

if __name__=="__main__":
    Metre()