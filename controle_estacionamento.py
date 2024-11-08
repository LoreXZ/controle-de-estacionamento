import cv2
import sqlite3
import time
import re

# Conectar ao banco de dados SQLite
conn = sqlite3.connect("estacionamento.db")
cursor = conn.cursor()

# Criar a tabela de cadastro
cursor.execute(""" 
CREATE TABLE IF NOT EXISTS veiculos (
    placa TEXT PRIMARY KEY,
    nome_cliente TEXT,
    modelo_carro TEXT,
    vezes_visita INTEGER DEFAULT 0,
    entrada TIMESTAMP,
    saida TIMESTAMP,
    valor_a_pagar REAL,
    pago INTEGER DEFAULT 0
)
""")
conn.commit()

# Função para validar a placa
def validar_placa(placa):
    # Verifica se a placa segue o formato AAA1A11
    return re.match(r'^[A-Z]{3}\d[A-Z]\d{2}$', placa) is not None

# Função para cadastrar novo veículo
def cadastrar_veiculo(placa, nome_cliente, modelo_carro):
    cursor.execute("SELECT * FROM veiculos WHERE placa = ?", (placa,))
    veiculo = cursor.fetchone()

    if veiculo:
        # Cliente já cadastrado, incrementar visitas
        vezes_visita = veiculo[3] + 1
        cursor.execute("""
            UPDATE veiculos SET vezes_visita = ?, entrada = ?, pago = 0 WHERE placa = ?
        """, (vezes_visita, time.time(), placa))
    else:
        # Novo cadastro
        cursor.execute("""
            INSERT INTO veiculos (placa, nome_cliente, modelo_carro, vezes_visita, entrada)
            VALUES (?, ?, ?, ?, ?)
        """, (placa, nome_cliente, modelo_carro, 1, time.time()))

    conn.commit()

# Função para registrar a saída
def registrar_saida(placa, valor_hora):
    cursor.execute("SELECT * FROM veiculos WHERE placa = ?", (placa,))
    veiculo = cursor.fetchone()

    if veiculo:
        entrada = veiculo[4]
        vezes_visita = veiculo[3]
        saida = time.time()
        tempo_passado = (saida - entrada) / 3600  # Converter para horas
        valor_a_pagar = tempo_passado * valor_hora if vezes_visita % 10 != 0 else 0  # Saída grátis a cada 10 visitas

        cursor.execute("""
            UPDATE veiculos
            SET saida = ?, valor_a_pagar = ?, pago = ?
            WHERE placa = ?
        """, (saida, valor_a_pagar, 1 if valor_a_pagar == 0 else 0, placa))

        conn.commit()
        return valor_a_pagar
    else:
        print("Veículo não encontrado.")
        return None

# Função para processar o pagamento
def processar_pagamento(placa):
    cursor.execute("SELECT valor_a_pagar FROM veiculos WHERE placa = ?", (placa,))
    valor_a_pagar = cursor.fetchone()

    if valor_a_pagar and valor_a_pagar[0] > 0:
        pagamento = int(input("Digite 1 se foi pago ou 2 se não foi: "))
        cursor.execute("UPDATE veiculos SET pago = ? WHERE placa = ?", (pagamento == 1, placa))
        conn.commit()
    else:
        print("Nenhum pagamento pendente ou saída gratuita por fidelidade.")

# Função para detectar rostos e identificar cliente (ajustada com verificação de câmera)
def detectar_rosto():
    # Carregar os classificadores em cascata
    RostoFrontal = cv2.CascadeClassifier('Haarcascade/haarcascade_frontalface_default.xml')
    RostoPerfil = cv2.CascadeClassifier('Haarcascade/haarcascade_profileface.xml')

    # Inicializar a captura de vídeo
    captura = cv2.VideoCapture(0)

    # Verificar se a captura foi iniciada corretamente
    if not captura.isOpened():
        print("Erro ao abrir o vídeo ou câmera.")
        exit()

    rosto_detectado = False  # Variável para verificar se algum rosto foi detectado

    while True:
        # Ler um quadro da câmera
        ret, imagem = captura.read()  # 'ret' é um valor booleano que indica se a captura foi bem-sucedida

        # Verificar se o quadro foi capturado corretamente
        if not ret:
            print("Não foi possível capturar o vídeo ou o final foi alcançado.")
            break

        # Redimensionar a imagem
        imagem = cv2.resize(imagem, (1240, 640))

        # Converter a imagem para escala de cinza
        imagemcinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

        # Detectar faces frontais
        faces_frontal = RostoFrontal.detectMultiScale(imagemcinza, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        # Detectar faces de perfil
        faces_perfil = RostoPerfil.detectMultiScale(imagemcinza, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        # Verificar se foram detectadas faces
        if len(faces_frontal) > 0 or len(faces_perfil) > 0:
            rosto_detectado = True

        # Desenhar retângulos ao redor das faces frontais detectadas
        for (x, y, l, a) in faces_frontal:
            cv2.rectangle(imagem, (x, y), (x + l, y + a), (255, 0, 0), 2)

        # Desenhar retângulos ao redor das faces de perfil detectadas
        for (x, y, l, a) in faces_perfil:
            if l > 40 and a > 40:
                cv2.rectangle(imagem, (x, y), (x + l, y + a), (0, 255, 0), 2)

        # Mostrar a imagem com as faces detectadas
        cv2.imshow("Faces", imagem)

        # Sair do loop se a tecla 'q' for pressionada
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    captura.release()
    cv2.destroyAllWindows()
    return rosto_detectado

# Função principal para controlar entrada e saída
def controle_estacionamento():
    while True:
        acao = input("Digite 'entrar' para novo veículo ou 'sair' para veículo saindo (pressione 'q' para sair do programa): ").strip().lower()

        if acao == "entrar":
            if detectar_rosto():
                print("Cliente reconhecido.")
                placa = input("Placa do carro (formato AAA1A11): ")

                if validar_placa(placa):
                    # Chamar a função de cadastro que já lida com ambos os casos
                    cadastrar_veiculo(placa, None, None)
                    cursor.execute("SELECT * FROM veiculos WHERE placa = ?", (placa,))
                    veiculo = cursor.fetchone()

                    if veiculo and veiculo[3] == 1:  # Se a contagem de visitas for 1, significa que é um novo cadastro
                        nome_cliente = str(input("Nome do cliente: "))
                        modelo_carro = str(input("Modelo do carro: "))
                        cursor.execute("""
                            UPDATE veiculos SET nome_cliente = ?, modelo_carro = ? WHERE placa = ?
                        """, (nome_cliente, modelo_carro, placa))
                        conn.commit()

                    print("Veículo registrado com sucesso.")
                else:
                    print("Placa inválida. A placa deve seguir o formato AAA1A11.")

            else:
                print("Nenhum rosto detectado. Tente novamente.")

        elif acao == "sair":
            placa = input("Placa do carro: ")
            valor_hora = float(input("Valor da hora: "))
            valor_a_pagar = registrar_saida(placa, valor_hora)

            if valor_a_pagar == 0:
                print("Saída gratuita por fidelidade!")
            elif valor_a_pagar is not None:
                print(f"Valor a ser pago: R$ {valor_a_pagar:.2f}")
                processar_pagamento(placa)
            else:
                print("Veículo não encontrado.")

        elif acao == "q":
            print("Saindo do programa...")
            break

        else:
            print("Ação inválida. Tente novamente.")

# Executar o controle de estacionamento
if __name__ == "__main__":
    controle_estacionamento()
