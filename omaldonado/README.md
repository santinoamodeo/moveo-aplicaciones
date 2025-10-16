---Codigo completo del proyecto Brazo Robotico Moveo + MQTT ---

El proyecto se basa en controlar el Brazo Moveo con MQTT, el lenguaje utilizado en este caso fue Python y la aplicacion fue MyMQTT
esto lo llevamos a cabo de la siguiente manera, se realizo un archivo llamado "Brazo.py" en este se encuentran los codigos de movimiento del Brazo, escritos en G-Code.
Luego encontramos un archivo llamada "Final.py" dentro de este se encuentra importado el modulo de del programa anterior, dentro de el programa "Final.py" se ejecutan las funciones 

Primero debemos entender el funcionamiento de MQTT y establecer un broker, en mi caso utilice uno que es publico de Google, una vez tenemos eso establecemos dentro del codigo el Topic en donde vayamos a establecer la comunicacion, a su vez con el celular debemos conectarnos mediante la aplicacion MyMQTT al broker y luego al Topic como publicador (envia mensaje), mientras
que el brazo va a estar suscripto a ese topico (lee el mensaje). Las secuencias de movimiento, velocidad, nombre del topico o nombre del comando son totalmente modificables, lo recomendado es adaptar cada variable a su brazo.

