# =================================================================================
# === SISTEMA DE GESTIÓN DE INVENTARIO POR VISIÓN CON ARUCO ===
# === Desarrollado por: Cristóbal Parra A. - IPP(2025) ===
# =================================================================================
#
# DESCRIPCIÓN GENERAL:
# Esta aplicación permite gestionar un inventario de piezas utilizando
# marcadores ArUco mediante visión por computador. El programa se divide en  
# tres etapas principales que se muestran en una interfaz interactiva:
#
# 1. Bienvenida: Presenta la aplicación y guía al usuario sobre su funcionamiento.
# 2. Clasificación: Permite al usuario "enseñar" al sistema a reconocer piezas.
#    Se muestra un marcador ArUco a la cámara y se le asocia una descripción
#    (modelo y tipo), que se guarda en una base de datos local.
# 3. Almacén: Utiliza la cámara para detectar los marcadores en una zona de almacenamiento
#    determinada. Identifica las piezas según la base de datos y muestra el estado
#    del inventario en tiempo real sobre una rejilla de detección configurable.
#
# =================================================================================

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import cv2.aruco as aruco
import numpy as np
from PIL import Image, ImageTk
import json
import os

# =================================================================================
# === SECCIÓN 1: PARÁMETROS GLOBALES Y FUNCIONES ===
# =================================================================================

# --- Definición de la paleta de colores y fuentes para la interfaz ---
BG_COLOR = "#2E2E2E"
FRAME_COLOR = "#3C3C3C"
TEXT_COLOR = "#FFFFFF"
BUTTON_BG = "#555555"
BUTTON_FG = TEXT_COLOR
SUCCESS_COLOR = "#28a745"
INFO_COLOR = "#17a2b8"
HIGHLIGHT_COLOR = "#ffc107"
FONT_NORMAL = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 11, "bold")
FONT_LARGE_BOLD = ("Segoe UI", 22, "bold")

# --- Archivo de la base de datos ---
DB_FILE = "piece_database.json"

def display_image_on_label(parent_widget, img, label):
   
    # Si el widget aún no se ha dibujado, su tamaño será 1. Se reintenta tras 20ms.
    if not label.winfo_exists() or label.winfo_width() <= 1:
        parent_widget.after(20, lambda: display_image_on_label(parent_widget, img, label))
        return
    
    h, w = img.shape[:2]
    # Calcula el ratio para redimensionar la imagen sin distorsionarla, ajustándose al Label.
    ratio = min(label.winfo_width() / w, label.winfo_height() / h)
    resized = cv2.resize(img, (int(w * ratio), int(h * ratio)), interpolation=cv2.INTER_AREA)
    
    # Convierte la imagen de BGR (OpenCV) a RGB y luego a un formato que Tkinter pueda usar.
    img_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_rgb)
    img_tk = ImageTk.PhotoImage(image=img_pil)
    
    # Actualiza el widget Label con la nueva imagen.
    label.imgtk = img_tk  # Guarda una referencia para evitar que el recolector de basura la elimine.
    label.configure(image=img_tk)

def load_piece_database():
    """Carga la base de datos de piezas desde el archivo JSON."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

# =================================================================================
# === SECCIÓN 2: BASE PRINCIPAL DE LA APLICACIÓN (APP) ===
# =================================================================================
# Gestiona la ventana principal y la transición entre las diferentes "pantallas" o etapas.
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Gestión de Inventario por Visión (ArUco) - Cristóbal Parra A. (2025)")
        self.config(bg=BG_COLOR)
        self.state('zoomed') # Inicia la ventana maximizada.
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Configuración de Estilos para Widgets ttk ---
        # Centraliza la apariencia de los widgets para un look consistente en toda la app.
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TEntry', fieldbackground='#555555', foreground=TEXT_COLOR, font=FONT_NORMAL, insertcolor=TEXT_COLOR, borderwidth=1, relief='sunken')
        style.configure('TCombobox', fieldbackground='#555555', foreground=TEXT_COLOR, font=FONT_NORMAL, selectbackground='#444444', arrowcolor=TEXT_COLOR)
        style.map('TCombobox', fieldbackground=[('readonly', '#555555')])
        style.configure('Treeview', background="#333333", foreground=TEXT_COLOR, font=FONT_NORMAL, fieldbackground="#333333", borderwidth=0)
        style.configure('Treeview.Heading', font=FONT_BOLD, background=BUTTON_BG, foreground=TEXT_COLOR, relief='flat')
        style.map("Treeview.Heading", relief=[('active','groove')])
        style.configure('TRadiobutton', background=FRAME_COLOR, foreground=TEXT_COLOR, font=FONT_NORMAL)
        style.map('TRadiobutton', background=[('active', FRAME_COLOR)])

        # --- Contenedor de Vistas ---
        # Un único contenedor que alojará los frames de cada etapa.
        container = tk.Frame(self, bg=BG_COLOR)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # --- Inicialización de los Frames (Etapas) ---
        self.frames = {}
        for F in (WelcomeScreen, ClassificationScreen, WarehouseScreen):
            frame = F(container, self)
            self.frames.setdefault(F, frame).grid(row=0, column=0, sticky="nsew")
        
        self.show_frame(WelcomeScreen) # Muestra la pantalla de bienvenida al iniciar.

    def show_frame(self, cont):
        """Muestra un frame (vista/etapa) específico y oculta los demás."""
        frame = self.frames.get(cont)
        if frame:
            # Antes de mostrar un nuevo frame, se oculta el anterior para liberar recursos (ej. la cámara).
            for f in self.frames.values():
                if f.winfo_ismapped() and hasattr(f, 'on_hide'): f.on_hide()
            # Muestra el frame solicitado.
            frame.tkraise()
            # Activa los recursos del nuevo frame (ej. la cámara).
            if hasattr(frame, 'on_show'): frame.on_show()

    def on_close(self):
        """Manejador para el cierre de la ventana principal."""
        # Se asegura de liberar todas las cámaras antes de cerrar la aplicación.
        for frame in self.frames.values():
            if hasattr(frame, 'release_camera'): frame.release_camera()
        self.destroy()

# =================================================================================
# === SECCIÓN 3: ETAPA 1 - PANTALLA DE BIENVENIDA ===
# =================================================================================
class WelcomeScreen(tk.Frame):
    """La pantalla inicial de la aplicación. Muestra el título, logo e instrucciones."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_COLOR)
        main_frame = tk.Frame(self, bg=BG_COLOR); main_frame.pack(expand=True, padx=20, pady=20)
        
        try:
            logo_pil = Image.open("UBB.png"); logo_pil.thumbnail((120, 120))
            self.logo_tk = ImageTk.PhotoImage(logo_pil)
            tk.Label(main_frame, image=self.logo_tk, bg=BG_COLOR).pack(pady=20)
        except FileNotFoundError:
            tk.Label(main_frame, text="Logo 'UBB.png' no encontrado", bg=BG_COLOR, fg=HIGHLIGHT_COLOR).pack(pady=15)
        
        tk.Label(main_frame, text="Gestión de Inventario con ArUco", font=("Segoe UI", 26, "bold"), bg=BG_COLOR, fg=INFO_COLOR).pack(pady=(10, 15))
        
        instructions_container = tk.Frame(main_frame, bg=FRAME_COLOR, bd=2, relief='sunken'); instructions_container.pack(pady=20, padx=30, fill="x")
        tk.Label(instructions_container, text="Guía Rápida de Uso", font=("Segoe UI", 14, "bold"), bg=FRAME_COLOR, fg=TEXT_COLOR).pack(pady=(10, 5))
        instructions_text = (
            "Bienvenido al Sistema de Inventario por Visión.\n\n"
            "Este programa utiliza marcadores ArUco para identificar y rastrear piezas en un almacén.\n"
            "Siga estos pasos para comenzar:\n\n"
            "1. Etapa de Clasificación: 'Enseñe' al sistema a reconocer cada pieza. Deberá mostrar\n"
            "     un marcador ArUco a la cámara y asociarlo con un nombre ('Modelo') y su 'Tipo'.\n\n"
            "2. Etapa de Almacén: Una vez clasificadas sus piezas, podrá monitorear su inventario.\n"
            "     Defina una rejilla sobre la imagen de su almacén y el sistema detectará qué pieza\n"
            "     ocupa cada espacio en tiempo real."
        )
        tk.Label(instructions_container, text=instructions_text, justify="left", wraplength=600, bg=FRAME_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 11)).pack(padx=20, pady=15)
        
        start_button = tk.Button(main_frame, text="Comenzar", command=lambda: controller.show_frame(ClassificationScreen), font=("Segoe UI", 16, "bold"), bg=SUCCESS_COLOR, fg="white", relief='flat', padx=30, pady=5)
        start_button.pack(pady=15)
        tk.Label(main_frame, text="Desarrollado por Cristóbal Parra A.", font=("Times New Roman", 15, "italic"), bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=10)
        tk.Label(main_frame, text="Ingeniería Civíl en Automatización.", font=("Segoe", 10, "italic"), bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=0)

# =================================================================================
# === SECCIÓN 4: ETAPA 2 - CLASIFICACIÓN DE PIEZAS (ARUCO) ===
# =================================================================================
class ClassificationScreen(tk.Frame):
    """Pantalla para clasificar piezas, asociando un ID de ArUco a un modelo y tipo."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_COLOR)
        self.controller = controller; self.cap = None; self.is_camera_active = False; self.flip_camera = False
        
        # --- Configuración del detector ArUco ---
        self.aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_5X5_100)
        self.aruco_params = aruco.DetectorParameters()
        self.aruco_params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
        
        self.highlighted_id = None # Para el resaltado visual al guardar.

        # --- Layout de la Interfaz ---
        main_frame = tk.Frame(self, bg=BG_COLOR, padx=20, pady=20); main_frame.pack(fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=2); main_frame.grid_columnconfigure(1, weight=1); main_frame.grid_rowconfigure(0, weight=1)
        
        camera_frame = tk.Frame(main_frame, bg=FRAME_COLOR, bd=2, relief='sunken'); camera_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.camera_label = tk.Label(camera_frame, bg="black"); self.camera_label.pack(fill="both", expand=True, padx=5, pady=5)
        
        controls_frame = tk.Frame(main_frame, bg=FRAME_COLOR, bd=2, relief='sunken', padx=15, pady=10); controls_frame.grid(row=0, column=1, sticky="nsew"); controls_frame.columnconfigure(0, weight=1)
        
        tk.Label(controls_frame, text="Clasificación de Marcadores", font=FONT_BOLD, bg=FRAME_COLOR, fg=TEXT_COLOR).grid(row=0, column=0, pady=10)
        tk.Label(controls_frame, text="ID de ArUco Detectado:", font=FONT_NORMAL, bg=FRAME_COLOR, fg=TEXT_COLOR).grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.detected_ids_combo = ttk.Combobox(controls_frame, font=FONT_NORMAL); self.detected_ids_combo.grid(row=2, column=0, sticky="ew", pady=5)
        tk.Label(controls_frame, text="Modelo de Pieza:", font=FONT_NORMAL, bg=FRAME_COLOR, fg=TEXT_COLOR).grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.model_entry = ttk.Entry(controls_frame, font=FONT_NORMAL); self.model_entry.grid(row=4, column=0, sticky="ew", pady=5)
        
        type_frame = tk.Frame(controls_frame, bg=FRAME_COLOR); type_frame.grid(row=5, column=0, sticky="ew", pady=5); type_frame.columnconfigure((0,1,2), weight=1)
        self.type_var = tk.StringVar(value="Macho")
        ttk.Radiobutton(type_frame, text="Macho", variable=self.type_var, value="Macho").grid(row=0, column=0, sticky='w')
        ttk.Radiobutton(type_frame, text="Hembra", variable=self.type_var, value="Hembra").grid(row=0, column=1)
        ttk.Radiobutton(type_frame, text="Ensamblada", variable=self.type_var, value="Ensamblada").grid(row=0, column=2, sticky='e')
        
        save_button = tk.Button(controls_frame, text="Guardar Clasificación", command=self.save_association, bg=SUCCESS_COLOR, fg="white", font=FONT_BOLD, relief='flat', padx=10, pady=5); save_button.grid(row=6, column=0, sticky="ew", pady=10)
        self.status_label = tk.Label(controls_frame, text="", bg=FRAME_COLOR, fg=HIGHLIGHT_COLOR, font=FONT_NORMAL); self.status_label.grid(row=7, column=0, sticky="ew", pady=5)
        
        tk.Label(controls_frame, text="Clasificaciones Guardadas", font=FONT_BOLD, bg=FRAME_COLOR, fg=TEXT_COLOR).grid(row=8, column=0, pady=(15, 5))
        self.db_tree = ttk.Treeview(controls_frame, columns=("ID", "Modelo", "Tipo"), show="headings"); self.db_tree.heading("ID", text="ID"); self.db_tree.column("ID", width=50, anchor='center', stretch=False); self.db_tree.heading("Modelo", text="Modelo"); self.db_tree.column("Modelo", width=120, anchor='center', stretch=True); self.db_tree.heading("Tipo", text="Tipo"); self.db_tree.column("Tipo", width=100, anchor='center', stretch=False); self.db_tree.grid(row=9, column=0, sticky="nsew", pady=5, padx=0); controls_frame.grid_rowconfigure(9, weight=1)
        
        delete_button = tk.Button(controls_frame, text="Eliminar Selección", command=self.delete_selected_associations, bg="#dc3545", fg="white", font=FONT_BOLD, relief='flat', padx=10, pady=5); delete_button.grid(row=10, column=0, sticky="ew", pady=(10,5))
        warehouse_button = tk.Button(controls_frame, text="Ir al Almacén >>", command=lambda: controller.show_frame(WarehouseScreen), bg=INFO_COLOR, fg="white", font=FONT_BOLD, relief='flat', padx=10, pady=5); warehouse_button.grid(row=11, column=0, sticky="ew", pady=5)

    def on_show(self): self.update_db_view(); self.activate_camera()
    def on_hide(self): self.release_camera()
    
    def activate_camera(self):
        if self.is_camera_active: return
        self.cap = cv2.VideoCapture(0)
        if self.cap.isOpened(): self.is_camera_active = True; self.update_loop()
    
    def release_camera(self): self.is_camera_active = False; self.cap.release() if self.cap else None
    
    def update_loop(self):
        if not self.is_camera_active or not self.cap or not self.cap.isOpened(): return
        ret, frame = self.cap.read()
        if ret:
            if self.flip_camera: frame = cv2.flip(frame, 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            corners, ids, _ = aruco.detectMarkers(gray, self.aruco_dict, parameters=self.aruco_params)
            
            detected_ids_list = []
            if ids is not None:
                ids_flat = ids.flatten()
                for i, corner in enumerate(corners):
                    current_id_str, color = str(ids_flat[i]), (0, 0, 255)
                    if current_id_str == self.highlighted_id: color = (23, 193, 255)
                    aruco.drawDetectedMarkers(frame, [corner], np.array([[ids_flat[i]]]), borderColor=color)
                detected_ids_list = sorted([str(id_val) for id_val in ids_flat])
            
            if set(detected_ids_list) != set(self.detected_ids_combo['values']):
                self.detected_ids_combo['values'] = detected_ids_list
                if detected_ids_list: self.detected_ids_combo.set(detected_ids_list[-1])
            
            display_image_on_label(self, frame, self.camera_label)
        self.after(30, self.update_loop)

    def save_association(self):
        aruco_id, model, p_type = self.detected_ids_combo.get(), self.model_entry.get(), self.type_var.get()
        if not aruco_id or not model: self.status_label.config(text="Error: Complete ID y Modelo."); return
        self.highlighted_id = aruco_id; self.after(2000, self.clear_highlight)
        db = load_piece_database(); found = False
        for entry in db:
            if 'aruco_id' in entry and entry['aruco_id'] == aruco_id: entry['model'], entry['type'], found = model, p_type, True; break
        if not found: db.append({"aruco_id": aruco_id, "model": model, "type": p_type})
        with open(DB_FILE, 'w') as f: json.dump(db, f, indent=4)
        self.status_label.config(text=f"ID {aruco_id} {'actualizado' if found else 'clasificado'}.")
        self.update_db_view(); self.model_entry.delete(0, tk.END)

    def clear_highlight(self): self.highlighted_id = None
    
    def update_db_view(self):
        self.db_tree.delete(*self.db_tree.get_children())
        for entry in load_piece_database():
            if all(k in entry for k in ['aruco_id', 'model', 'type']): self.db_tree.insert("", "end", values=(entry['aruco_id'], entry['model'], entry['type']))
    
    def delete_selected_associations(self):
        selected_items = self.db_tree.selection()
        if not selected_items: messagebox.showinfo("Selección Requerida", "Por favor, selecciona las clasificaciones a eliminar."); return
        if messagebox.askyesno("Confirmar Eliminación", f"¿Eliminar {len(selected_items)} clasificaciones seleccionadas?"):
            db = load_piece_database(); ids_to_delete = {str(self.db_tree.item(item)['values'][0]) for item in selected_items}
            updated_db = [entry for entry in db if str(entry.get('aruco_id')) not in ids_to_delete]
            with open(DB_FILE, 'w') as f: json.dump(updated_db, f, indent=4)
            self.update_db_view(); self.status_label.config(text=f"{len(ids_to_delete)} clasificaciones eliminadas.")

# =================================================================================
# === SECCIÓN 5: ETAPA 3 - GESTIÓN DE ALMACÉN (ARUCO) ===
# =================================================================================
class WarehouseScreen(tk.Frame):
    """Pantalla para la gestión del inventario en tiempo real usando una rejilla configurable."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_COLOR)
        self.controller = controller; self.cap = None; self.is_camera_active = False; self.piece_db = {}; self.flip_camera = False
        self.aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_5X5_100); self.aruco_params = aruco.DetectorParameters(); self.aruco_params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
        
        # --- Layout de la Interfaz ---
        top_controls = tk.Frame(self, bg=BG_COLOR, pady=10, padx=20); top_controls.pack(fill="x")
        top_controls.grid_columnconfigure(0, weight=1)
        
        # Contenedor para los sliders en una matriz 2x2 a la izquierda
        sliders_frame = tk.Frame(top_controls, bg=BG_COLOR); sliders_frame.grid(row=0, column=0, sticky='w')
        sliders_frame.grid_columnconfigure((0, 1), weight=1)

        def create_slider(parent, text, from_, to, initial_val):
            container = tk.Frame(parent, bg=BG_COLOR)
            tk.Label(container, text=text, bg=BG_COLOR, fg=TEXT_COLOR, font=FONT_NORMAL).pack(pady=(10, 0))
            slider = tk.Scale(container, from_=from_, to=to, orient="horizontal", bg=BG_COLOR, fg=TEXT_COLOR, troughcolor=BUTTON_BG, highlightthickness=0, length=1000)
            slider.set(initial_val); slider.pack(fill='x', expand=True)
            return slider
        self.x_offset_var = create_slider(sliders_frame, "Offset X", 0, 1000, 40); self.x_offset_var.master.grid(row=0, column=0, padx=10, sticky='ew')
        self.y_offset_var = create_slider(sliders_frame, "Offset Y", 0, 1000, 10); self.y_offset_var.master.grid(row=0, column=1, padx=10, sticky='ew')
        self.grid_width_var = create_slider(sliders_frame, "Ancho Rejilla", 100, 1500, 1200); self.grid_width_var.master.grid(row=1, column=0, padx=10, sticky='ew')
        self.grid_height_var = create_slider(sliders_frame, "Alto Rejilla", 100, 1000, 700); self.grid_height_var.master.grid(row=1, column=1, padx=10, sticky='ew')
        
        # Contenedor para el botón de volver y las dimensiones a la derecha
        right_controls = tk.Frame(top_controls, bg=BG_COLOR); right_controls.grid(row=0, column=1, sticky='e', padx=20)
        tk.Button(right_controls, text="<< Volver a Clasificación", command=lambda: controller.show_frame(ClassificationScreen), bg=BUTTON_BG, fg=BUTTON_FG, font=FONT_BOLD, relief='flat', padx=10, pady=5).pack(pady=(0, 10))
        dims_frame = tk.Frame(right_controls, bg=FRAME_COLOR, bd=1, relief='sunken'); dims_frame.pack(anchor='e')
        self.rows_var = tk.IntVar(value=3); self.cols_var = tk.IntVar(value=4)
        tk.Label(dims_frame, text="Filas:", bg=FRAME_COLOR, fg=TEXT_COLOR, font=FONT_NORMAL).pack(side="left", padx=(10,5), pady=5)
        ttk.Entry(dims_frame, textvariable=self.rows_var, width=5, font=FONT_NORMAL).pack(side="left", padx=5, pady=5)
        tk.Label(dims_frame, text="Columnas:", bg=FRAME_COLOR, fg=TEXT_COLOR, font=FONT_NORMAL).pack(side="left", padx=(10,5), pady=5)
        ttk.Entry(dims_frame, textvariable=self.cols_var, width=5, font=FONT_NORMAL).pack(side="left", padx=10, pady=5)

        # Panel de contenido principal
        main_content_frame = tk.Frame(self, bg=BG_COLOR, padx=20, pady=10); main_content_frame.pack(fill="both", expand=True)
        main_content_frame.grid_columnconfigure(0, weight=2); main_content_frame.grid_columnconfigure(1, weight=1); main_content_frame.grid_rowconfigure(0, weight=1)
        self.camera_label = tk.Label(main_content_frame, bg="black"); self.camera_label.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.status_grid_frame = tk.Frame(main_content_frame, bg=FRAME_COLOR, bd=2, relief='sunken'); self.status_grid_frame.grid(row=0, column=1, sticky="nsew")
        self.status_labels = {}
        
    def on_show(self):
        db_list = load_piece_database(); self.piece_db = {entry['aruco_id']: entry for entry in db_list if 'aruco_id' in entry}
        self.setup_status_grid(); self.activate_camera()
    def on_hide(self): self.release_camera()
    def activate_camera(self):
        if self.is_camera_active: return
        self.cap = cv2.VideoCapture(0)
        if self.cap.isOpened(): self.is_camera_active = True; self.update_warehouse_view()
    def release_camera(self): self.is_camera_active = False; self.cap.release() if self.cap else None
    
    def setup_status_grid(self):
        for widget in self.status_grid_frame.winfo_children(): widget.destroy()
        self.status_labels = {}
        try: rows, cols = self.rows_var.get(), self.cols_var.get()
        except tk.TclError: rows, cols = 3, 3
        if rows <= 0 or cols <= 0: return
        for r in range(rows):
            self.status_grid_frame.rowconfigure(r, weight=1)
            for c in range(cols):
                self.status_grid_frame.columnconfigure(c, weight=1)
                lbl = tk.Label(self.status_grid_frame, text="Vacío", bg=FRAME_COLOR, fg="white", font=FONT_NORMAL, relief='sunken', bd=1, wraplength=120)
                lbl.grid(row=r, column=c, padx=2, pady=2, sticky="nsew"); self.status_labels[(r, c)] = lbl
    
    def update_warehouse_view(self):
        if not self.is_camera_active or not self.cap or not self.cap.isOpened(): return
        ret, frame = self.cap.read()
        if ret:
            if self.flip_camera: frame = cv2.flip(frame, 1)
            self.draw_grid_and_analyze(frame)
            display_image_on_label(self, frame, self.camera_label)
        self.after(50, self.update_warehouse_view)
        
    def draw_grid_and_analyze(self, frame):
        try:
            rows, cols = self.rows_var.get(), self.cols_var.get()
            if rows <= 0 or cols <= 0: raise tk.TclError
        except tk.TclError: self.setup_status_grid(); return
        
        current_cols, current_rows = self.status_grid_frame.grid_size()
        if rows != current_rows or cols != current_cols: self.setup_status_grid()
        
        x0, y0 = self.x_offset_var.get(), self.y_offset_var.get(); grid_w, grid_h = self.grid_width_var.get(), self.grid_height_var.get()
        cell_w, cell_h = (grid_w / cols) if cols > 0 else 0, (grid_h / rows) if rows > 0 else 0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY); corners, ids, _ = aruco.detectMarkers(gray, self.aruco_dict, parameters=self.aruco_params)
        
        id_locations = {}
        if ids is not None:
            aruco.drawDetectedMarkers(frame, corners, ids, borderColor=(0, 0, 255))
            for i, corner_set in enumerate(corners):
                cx, cy = int(np.mean(corner_set[0][:, 0])), int(np.mean(corner_set[0][:, 1]))
                if x0 <= cx < x0 + grid_w and y0 <= cy < y0 + grid_h:
                    c_idx, r_idx = int((cx - x0) / cell_w), int((cy - y0) / cell_h)
                    if r_idx < rows and c_idx < cols: id_locations[(r_idx, c_idx)] = str(ids.flatten()[i])
        
        for r in range(rows):
            for c in range(cols):
                x1, y1 = int(x0 + c * cell_w), int(y0 + r * cell_h); x2, y2 = int(x1 + cell_w), int(y1 + cell_h)
                text, color, rect_color = "Vacío", FRAME_COLOR, (80, 80, 80)
                if (r, c) in id_locations:
                    found_id = id_locations[(r, c)]
                    if piece := self.piece_db.get(found_id):
                        text, color, rect_color = f"{piece['model']}\n ({piece['type']})\nID: {found_id}", SUCCESS_COLOR, (0, 255, 0)
                    else:
                        text, color, rect_color = f"ID: {found_id}\n(No asociado)", HIGHLIGHT_COLOR, (0, 191, 255)
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), rect_color, 1)
                if (r, c) in self.status_labels: self.status_labels[(r, c)].config(text=text, bg=color)

# =================================================================================
# === SECCIÓN 6: PUNTO DE ENTRADA DE LA APLICACIÓN ===
# =================================================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()
# =================================================================================
