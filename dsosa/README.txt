Ejercicio1Completo es un archivo realizado en código g, el cual mediante Python se envia por serial a un Arduino mega con Marlin
para simular movimientos de un brazo robotico industrial real. Este código hace que el brazo sea capaz de buscar un objeto en 
un extremo de la emsa, agarrarlo y dejarlo en el otro extremo, y volver a su posición de reposo, desactivando los motores evitando
que estos se calienten al estar siempre energizados
Posición de reposo: El brazo debe de estar completamente recto, con todas las marcas de los ejes alineadas, y es desde esta posición
de donde esta escrito el código g para que se mueva hacia un lado o hacia al otro. 