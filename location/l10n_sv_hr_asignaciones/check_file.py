import os

def check_file():
    # Ruta relativa desde la raíz del módulo
    relative_path = 'static/plantilla_horas_extra.xlsx'

    # Obtener ruta absoluta según este script
    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, relative_path)

    print(f"Buscando archivo en (ruta absoluta): {file_path}")

    if os.path.isfile(file_path):
        print("El archivo existe.")
        try:
            with open(file_path, 'rb') as f:
                data = f.read(10)  # Leer primeros 10 bytes solo para prueba
            print("Archivo leído correctamente. Primeros 10 bytes:", data)
        except Exception as e:
            print("Error al abrir el archivo:", e)
    else:
        print("¡El archivo NO existe en esta ruta!")

if __name__ == "__main__":
    check_file()
