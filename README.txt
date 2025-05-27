# TradeMotor

TradeMotor es un programa para la compra y venta de coches de segunda mano, desarrollada con Flask, MariaDB y MongoDB.

## Características principales

- Registro e inicio de sesión de usuarios (comprador/vendedor)
- Publicación de anuncios de coches con imágenes y detalles avanzados
- Filtros avanzados de búsqueda (tipo, autonomía, batería, etc.)
- Sistema de favoritos y comentarios
- Ofertas y gestión de ventas entre usuarios
- Historial de precios y transacciones

## Instalación

1. Clona el repositorio y navega a la carpeta del proyecto.
2. Instala las dependencias:
   ```sh
   pip install -r requirements.txt
   ```
3. Configura las conexiones a MariaDB y MongoDB en `appv2.py` según tu entorno.
4. Asegúrate de tener las bases de datos y tablas necesarias creadas. (se encuentran en la documenación.)

## Ejecución

Lanza la aplicación con:
```sh
python appv2.py
```
Accede a [http://localhost:5000](http://localhost:5000) en tu navegador.

## Estructura del proyecto

- `appv2.py`: Código principal de la aplicación Flask
- `templates/`: Plantillas HTML
- `static/`: Archivos estáticos (CSS, imágenes)
- `requirements.txt`: Dependencias del proyecto

## Autor

Iker Vericat Pastor

---

Este proyecto es solo para fines educativos.