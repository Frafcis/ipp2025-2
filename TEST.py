# =================================================================================
# APLICACIÓN DE VISIÓN POR COMPUTADOR PARA CONTEO DE OBJETOS - IPP 2025

# Realiza la detección y conteo de objetos en tiempo real o desde un archivo,
# mostrando los resultados en una interfaz gráfica interactiva creada con Tkinter.
# =================================================================================

# --- LIBRERÍAS Y MÓDULOS ---
# Se importan las librerías necesarias para la GUI, el manejo de imágenes y la visión por computador.
import tkinter as tk
from tkinter import Scale, filedialog, ttk
from PIL import Image, ImageTk
import cv2
import numpy as np

# --- CONSTANTES Y VARIABLES GLOBALES ---
# Define los colores de la interfaz, parámetros de detección y variables
BG_COLOR = "#2E2E2E"
TEXT_COLOR = "#FFFFFF"
BUTTON_COLOR = "#424242"
FRAME_COLOR = "#212121"
MIN_AREA_MANCHA = 200

capture = None
is_camera_running = False
source_image = None
# Variables de la grilla
x_offset_var = None
y_offset_var = None
grid_width_var = None
grid_height_var = None
rows_var = None
cols_var = None
status_grid_frame = None
status_labels = {}  # Aseguramos que esta variable global esté inicializada

# =================================================================================
# === FUNCIONES DE LÓGICA Y PROCESAMIENTO ===
# =================================================================================

# --- Control de Cámara ---
# Inicia y detiene la captura de video, gestionando el estado de los botones de la GUI.
def control_camara(iniciar=True):
    global capture, is_camera_running
    if iniciar:
        if is_camera_running: return
        for i in [0]:
            capture = cv2.VideoCapture(i)
            if capture.isOpened(): break
        if not capture or not capture.isOpened():
            print("ADVERTENCIA: No se pudo acceder a la cámara.")
            return
        is_camera_running = True
        btn_start.config(state="disabled"); btn_stop.config(state="normal"); btn_load.config(state="disabled")
        update_frame()
    else:
        is_camera_running = False
        if capture: capture.release()
        btn_start.config(state="normal"); btn_stop.config(state="disabled"); btn_load.config(state="normal")

# --- Bucle de Video en Tiempo Real ---
# Función recursiva que se ejecuta continuamente para leer frames de la cámara
# y mantener la imagen de video actualizada en la interfaz.
def update_frame():
    global source_image
    if is_camera_running:
        ret, frame = capture.read()
        if ret:
            source_image = cv2.flip(frame, 1)
            process_frame(source_image)
        ventana.after(20, update_frame)

# --- Carga de Imagen Estática ---
# Abre un explorador de archivos para que el usuario seleccione una imagen del disco
def cargar_imagen():
    global source_image
    if is_camera_running: control_camara(iniciar=False)
    path_image = filedialog.askopenfilename(filetypes=[("Archivos de imagen", "*.jpg *.jpeg *.png")])
    if path_image:
        source_image = cv2.imread(path_image)
        if source_image is not None: process_frame(source_image)

# --- Procesamiento de Imagen ---
# Núcleo del programa. Aplica una secuencia de filtros de OpenCV (escala de grises,
# desenfoque, umbralización) para detectar los contornos de los objetos, los filtra
# por área para eliminar ruido y finalmente dibuja los resultados sobre las imágenes.
def process_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    thresholded = cv2.inRange(blurred, slider_umbral_up.get(), slider_umbral_down.get())
    contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    manchas_reales = [c for c in contours if cv2.contourArea(c) > MIN_AREA_MANCHA]
    lbl_conteo.config(text=f"MANCHAS ENCONTRADAS: {len(manchas_reales)}")
    img_entrada_con_resultados = frame.copy()
    img_umbral_con_resultados = cv2.cvtColor(thresholded, cv2.COLOR_GRAY2RGB)

    # Lógica de la grilla
    matriz_estado = check_grid_status(img_entrada_con_resultados, manchas_reales)
    update_status_grid(matriz_estado)
    draw_grid_on_frame(img_entrada_con_resultados)

    for i, c in enumerate(manchas_reales):
        cv2.drawContours(img_umbral_con_resultados, [c], -1, (0, 255, 0), 2)
        x, y, w, h = cv2.boundingRect(c)
        cv2.rectangle(img_entrada_con_resultados, (x, y), (x + w, y + h), (0, 255, 0), 2)
        M = cv2.moments(c)
        cX = int(M["m10"] / M["m00"]) if M["m00"] != 0 else x
        cY = int(M["m01"] / M["m00"]) if M["m00"] != 0 else y
        cv2.putText(img_entrada_con_resultados, str(i + 1), (cX - 10, cY + 10), cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 0, 255), 2)
        cv2.putText(img_umbral_con_resultados, str(i + 1), (cX - 10, cY + 10), cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 0, 255), 2)
    display_image(img_entrada_con_resultados, lbl_original)
    display_image(img_umbral_con_resultados, lbl_umbralizada)

# --- Funciones de la grilla
def setup_status_grid():
    global status_labels
    if status_grid_frame is None: return
    for widget in status_grid_frame.winfo_children(): widget.destroy()
    status_labels = {}
    try:
        rows = int(rows_var.get())
        cols = int(cols_var.get())
        if rows <= 0 or cols <= 0: raise ValueError("Filas y columnas deben ser mayores a cero.")
    except (tk.TclError, ValueError) as e:
        print(f"Error al obtener dimensiones de la grilla: {e}. Usando valores predeterminados (3x4).")
        rows, cols = 3, 4
        rows_var.set(rows)
        cols_var.set(cols)
    
    for r in range(rows):
        status_grid_frame.rowconfigure(r, weight=1)
        for c in range(cols):
            status_grid_frame.columnconfigure(c, weight=1)
            lbl = tk.Label(status_grid_frame, text="Vacío", bg=FRAME_COLOR, fg="white", relief='sunken', bd=1, wraplength=120)
            lbl.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
            status_labels[(r, c)] = lbl

def check_grid_status(frame, contours):
    try:
        rows = int(rows_var.get())
        cols = int(cols_var.get())
        if rows <= 0 or cols <= 0: raise ValueError("Filas y columnas deben ser mayores a cero.")
    except (tk.TclError, ValueError):
        rows, cols = 3, 4 # Usar valores predeterminados si hay error
    
    matriz_estado = np.zeros((rows, cols), dtype=int)
    
    x0, y0 = x_offset_var.get(), y_offset_var.get()
    grid_w, grid_h = grid_width_var.get(), grid_height_var.get()

    if cols == 0 or rows == 0: # Evitar división por cero
        return matriz_estado

    cell_w, cell_h = grid_w / cols, grid_h / rows

    for c in contours:
        M = cv2.moments(c)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])

            # Check if centroid is within the grid area
            if x0 <= cX < x0 + grid_w and y0 <= cY < y0 + grid_h:
                c_idx = int((cX - x0) / cell_w)
                r_idx = int((cY - y0) / cell_h)

                if 0 <= r_idx < rows and 0 <= c_idx < cols: # Asegurarse de que los índices estén dentro de los límites
                    matriz_estado[r_idx, c_idx] = 1

    return matriz_estado

def update_status_grid(matriz_estado):
    global status_labels
    
    current_rows, current_cols = 0, 0
    if status_grid_frame:
        try:
            current_rows = status_grid_frame.grid_size()[0]
            current_cols = status_grid_frame.grid_size()[1]
        except Exception:
            pass # Si el grid no tiene tamaño aún, esto es normal

    new_rows, new_cols = matriz_estado.shape if matriz_estado.ndim == 2 else (0, 0)

    # Si las dimensiones de la matriz de estado son diferentes a las del grid actual, reconstruir el grid
    if new_rows != current_rows or new_cols != current_cols:
        setup_status_grid()

    for r in range(new_rows):
        for c in range(new_cols):
            text = "Ocupado" if matriz_estado[r, c] == 1 else "Vacío"
            bg_color = "#4CAF50" if matriz_estado[r, c] == 1 else FRAME_COLOR # Verde para ocupado, gris oscuro para vacío
            if (r, c) in status_labels:
                status_labels[(r, c)].config(text=text, bg=bg_color)
            else:
                # Esto no debería ocurrir si setup_status_grid() se llama correctamente
                print(f"Advertencia: Label para ({r}, {c}) no encontrado.")

def draw_grid_on_frame(frame):
    try:
        rows = int(rows_var.get())
        cols = int(cols_var.get())
        if rows <= 0 or cols <= 0: raise ValueError("Filas y columnas deben ser mayores a cero.")
    except (tk.TclError, ValueError):
        return # No dibujar si las dimensiones no son válidas

    x0, y0 = x_offset_var.get(), y_offset_var.get()
    grid_w, grid_h = grid_width_var.get(), grid_height_var.get()

    cell_w, cell_h = grid_w / cols, grid_h / rows

    # Dibujar líneas horizontales
    for r in range(rows + 1):
        y = int(y0 + r * cell_h)
        cv2.line(frame, (x0, y), (x0 + grid_w, y), (0, 255, 255), 1) # Color cian para la grilla

    # Dibujar líneas verticales
    for c in range(cols + 1):
        x = int(x0 + c * cell_w)
        cv2.line(frame, (x, y0), (x, y0 + grid_h), (0, 255, 255), 1) # Color cian para la grilla

# --- Visualización de Imagen en GUI ---
# Convierte una imagen de formato OpenCV a un formato compatible con la librería
# Tkinter (a través de Pillow) y la muestra en una etiqueta de la interfaz.
def display_image(img_cv, label):
    h, w = img_cv.shape[:2]
    new_width = 500
    ratio = new_width / float(w)
    dim = (new_width, int(h * ratio))
    img_resized = cv2.resize(img_cv, dim, interpolation=cv2.INTER_AREA)
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB if len(img_resized.shape) == 3 else cv2.COLOR_GRAY2RGB)
    img_pil = Image.fromarray(img_rgb)
    img_tk = ImageTk.PhotoImage(image=img_pil)
    label.configure(image=img_tk)
    label.image = img_tk

# --- Cierre Seguro de la Aplicación ---
# Se asegura de que la cámara se libere correctamente.
def on_closing():
    control_camara(iniciar=False)
    ventana.destroy()

# --- Relleno de espacios vacios en la webera ---
import serial
import time
SerialPort1 = serial.Serial()
def rellenar_vacios(vacios):
    if SerialPort1.isOpen() == False: #CAMBIAR A FALSE PARA PROBAR
        SerialPort1.baudrate = 9600
        SerialPort1.bytesize = 8
        SerialPort1.parity = "N"
        SerialPort1.stopbits = serial.STOPBITS_ONE
        SerialPort1.port = 'COM3'
        SerialPort1.open()

    for i,j in vacios:
        if i == 0: 
            matriz_pos[i][j]
            SerialPort1.write(b"Run 1" + b"\r")
            time.sleep(2)

    return
# =================================================================================
# === CONSTRUCCIÓN DE LA INTERFAZ GRÁFICA (GUI) ===
# =================================================================================

# --- Ventana Principal ---
# Creación y configuración de la ventana raíz de la aplicación.
ventana = tk.Tk()
ventana.title("Contabilizador de Manchas en Tiempo Real")
ventana.config(bg=BG_COLOR)
ventana.protocol("WM_DELETE_WINDOW", on_closing)

# --- Visores de Imágenes ---
# Creación de los marcos y etiquetas donde se mostrarán los videos.
frame_imagenes = tk.Frame(ventana, bg=BG_COLOR)
frame_imagenes.pack(pady=10, padx=10, fill='x', expand=True)

lbl_original = tk.Label(bg="black")
lbl_umbralizada = tk.Label(bg="black")
visores = [("1. Imagen Real", lbl_original), ("2. Imagen Umbralizada", lbl_umbralizada)]

for titulo, visor_label in visores:
    frame = tk.Frame(frame_imagenes, bg=FRAME_COLOR, bd=1, relief='sunken')
    frame.pack(side='left', padx=10, fill='x', expand=True)
    tk.Label(frame, text=titulo, font=("Times New Roman", 12, "bold"), bg=FRAME_COLOR, fg=TEXT_COLOR).pack(pady=(5,0))
    visor_label.pack(in_=frame, padx=5, pady=5)

# --- Panel de Controles Inferior ---
# Estructura de tres columnas para organizar los botones, el slider y los créditos.
frame_controles_inferior = tk.Frame(ventana, bg=BG_COLOR)
frame_controles_inferior.pack(pady=10, padx=10, fill='x', expand=True)

# Columna 1: Botones 
col1 = tk.Frame(frame_controles_inferior, bg=BG_COLOR)
col1.pack(side='left', fill='both', expand=True)
btn_start = tk.Button(col1, text="Detección Automatica", command=lambda: control_camara(True), font=("Times New Roman", 12), width=18, bg=BUTTON_COLOR, fg=TEXT_COLOR, relief='flat', activebackground='#555555', activeforeground=TEXT_COLOR)
btn_start.pack(pady=5)
btn_stop = tk.Button(col1, text="Detener Detección", command=lambda: control_camara(False), font=("Times New Roman", 12), width=18, state="disabled", bg=BUTTON_COLOR, fg=TEXT_COLOR, relief='flat', activebackground='#555555', activeforeground=TEXT_COLOR)
btn_stop.pack(pady=5)
btn_load = tk.Button(col1, text="Cargar Imagen", command=cargar_imagen, font=("Times New Roman", 12), width=18, bg=BUTTON_COLOR, fg=TEXT_COLOR, relief='flat', activebackground='#555555', activeforeground=TEXT_COLOR)
btn_load.pack(pady=5)
btn_fill = tk.Button(col1, text="Rellenar vacíos", command=lambda: rellenar_vacios([[1,0,1],[0,1,0]]), font=("Times New Roman", 12), width=18, bg=BUTTON_COLOR, fg=TEXT_COLOR, relief='flat', activebackground='#555555', activeforeground=TEXT_COLOR)
btn_fill.pack(pady=5)

# Columna 2: Contador y Slider de Ajuste
col2 = tk.Frame(frame_controles_inferior, bg=BG_COLOR)
col2.pack(side='left', fill='both', expand=True)
lbl_conteo = tk.Label(col2, text="MANCHAS ENCONTRADAS:", font=("Times New Roman", 22, "bold"), fg="#4FC3F7", bg=BG_COLOR)
lbl_conteo.pack(pady=(5, 10))
tk.Label(col2, text="Ajuste de Umbral:", font=("Times New Roman", 12), bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=(5,0))
slider_umbral_up = Scale(col2, from_=0, to=255, orient='horizontal', length=250, bg=BG_COLOR, fg=TEXT_COLOR, troughcolor='#757575', highlightthickness=0, activebackground=BUTTON_COLOR, 
                    command=lambda e: process_frame(source_image) if source_image is not None else None)
slider_umbral_up.set(127)
slider_umbral_up.pack(pady=(0, 5))

slider_umbral_down = Scale(col2, from_=0, to=255, orient='horizontal', length=250, bg=BG_COLOR, fg=TEXT_COLOR, troughcolor='#757575', highlightthickness=0, activebackground=BUTTON_COLOR, 
                    command=lambda e: process_frame(source_image) if source_image is not None else None)
slider_umbral_down.set(127)
slider_umbral_down.pack(pady=(0, 5))

# Columna 3: Créditos e Información
col3 = tk.Frame(frame_controles_inferior, bg=BG_COLOR)
col3.pack(side='left', fill='both', expand=True)
try:
    logo_pil = Image.open("UBB.png")
    h, w = logo_pil.height, logo_pil.width
    logo_resized = logo_pil.resize((int(60 * (w/h)), 60), Image.Resampling.LANCZOS)
    logo_tk = ImageTk.PhotoImage(logo_resized)
    lbl_logo = tk.Label(col3, image=logo_tk, bg=BG_COLOR)
    lbl_logo.image = logo_tk
    lbl_logo.pack(pady=(1,0)) 
except FileNotFoundError:
    tk.Label(col3, text="Logo 'UBB.png' no encontrado", font=("Times New Roman", 8), bg=BG_COLOR, fg="yellow").pack(pady=5)
tk.Label(col3, text="Desarrollado por Cristóbal Parra A.", font=("Times New Roman", 10), bg=BG_COLOR, fg=TEXT_COLOR).pack()
tk.Label(col3, text="Ingeniería Civil en Automatización", font=("Times New Roman", 9, "italic"), bg=BG_COLOR, fg=TEXT_COLOR).pack()
tk.Label(col3, text="2025-1", font=("Times New Roman", 9, "italic"), bg=BG_COLOR, fg=TEXT_COLOR).pack()

# --- Panel de Grilla y Estado ---
frame_grilla = tk.Frame(ventana, bg=BG_COLOR)
frame_grilla.pack(pady=10, padx=10, fill='x', expand=True)

# Controles de la grilla
grid_controls_frame = tk.Frame(frame_grilla, bg=BG_COLOR)
grid_controls_frame.pack(side='left', fill='y')

def create_slider(parent, text, from_, to, initial_val):
    container = tk.Frame(parent, bg=BG_COLOR)
    tk.Label(container, text=text, bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=(10, 0))
    slider = tk.Scale(container, from_=from_, to=to, orient='horizontal', length=200, bg=BG_COLOR, fg=TEXT_COLOR, troughcolor='#757575', highlightthickness=0, activebackground=BUTTON_COLOR, 
                      command=lambda e: process_frame(source_image) if source_image is not None else None)
    slider.set(initial_val)
    slider.pack(fill='x', expand=True)
    return slider

x_offset_var = create_slider(grid_controls_frame, "Offset X", 0, 1000, 40)
y_offset_var = create_slider(grid_controls_frame, "Offset Y", 0, 1000, 10)
grid_width_var = create_slider(grid_controls_frame, "Ancho Rejilla", 100, 1500, 400)
grid_height_var = create_slider(grid_controls_frame, "Alto Rejilla", 100, 1000, 300)

dims_frame = tk.Frame(grid_controls_frame, bg=FRAME_COLOR, bd=1, relief='sunken')
dims_frame.pack(pady=10)

rows_var = tk.StringVar(value="2")
cols_var = tk.StringVar(value="3")

def on_dimension_change(event=None): # Acepta un argumento opcional para que funcione con bind
    setup_status_grid()
    if source_image is not None:
        process_frame(source_image)

tk.Label(dims_frame, text="Filas:", bg=FRAME_COLOR, fg=TEXT_COLOR).pack(side="left", padx=(10,5), pady=5)
entry_rows = ttk.Entry(dims_frame, textvariable=rows_var, width=5)
entry_rows.pack(side="left", padx=5, pady=5)
entry_rows.bind('<Return>', on_dimension_change) # Bind para que al presionar Enter se actualice

tk.Label(dims_frame, text="Columnas:", bg=FRAME_COLOR, fg=TEXT_COLOR).pack(side="left", padx=(10,5), pady=5)
entry_cols = ttk.Entry(dims_frame, textvariable=cols_var, width=5)
entry_cols.pack(side="left", padx=10, pady=5)
entry_cols.bind('<Return>', on_dimension_change) # Bind para que al presionar Enter se actualice

# Matriz de estado
status_grid_frame = tk.Frame(frame_grilla, bg=FRAME_COLOR, bd=2, relief='sunken')
status_grid_frame.pack(side='right', fill="both", expand=True, padx=20)
setup_status_grid() # Inicializa la grilla al arrancar

# --- INICIO DE LA APLICACIÓN ---
ventana.mainloop()
