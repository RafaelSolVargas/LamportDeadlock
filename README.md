# Simulação de Detecção de Deadlock com Snapshot Distribuído - INE5418

Este projeto é uma simulação em Python que demonstra a detecção de deadlocks (impasses) em um ambiente concorrente, modelado como um Sistema de Gerenciamento de Banco de Dados (SGBD) simplificado.

O algoritmo central utilizado para a detecção é uma adaptação do **Snapshot Distribuído de Chandy-Lamport**, que permite capturar um estado global consistente do sistema sem interromper sua execução.

## Como Funciona

1.  **Clientes e Recursos:** A simulação cria múltiplos "clientes" (`ClientConnection`), que são threads, competindo por um conjunto de "tabelas" (`Table`), que são os recursos.
2.  **Operações:** Cada cliente executa continuamente operações de Leitura (`READ`) ou Escrita (`WRITE`).
    * **Leituras** não bloqueiam recursos.
    * **Escritas** exigem um lock exclusivo na(s) tabela(s), impedindo que outros clientes escrevam nela(s) ao mesmo tempo.
3.  **Contenção:** A simulação é projetada para que os clientes, ocasionalmente, tentem realizar transações que exigem locks em duas tabelas. Quando dois ou mais clientes tentam adquirir os mesmos locks em ordens diferentes, um deadlock pode ocorrer.
4.  **Monitoramento (Snapshot):** Uma thread dedicada (`Snapshotter`) captura periodicamente um "snapshot" do estado de todo o sistema. Este snapshot registra quais tabelas cada cliente possui e por qual tabela cada cliente está esperando.
5.  **Detecção de Deadlock:** O `DeadlockDetector` analisa o snapshot, construindo um **Grafo de Espera** (Wait-For Graph). Se um ciclo é encontrado neste grafo (ex: Cliente A espera por B, e B espera por A), um deadlock é confirmado.
6.  **Encerramento:** Ao detectar um deadlock, o sistema sinaliza um evento de desligamento global, e a aplicação encerra sua execução de forma limpa.

## Estrutura do Projeto

O código é organizado nos seguintes módulos:

-   `main.py`: O ponto de entrada da aplicação. Responsável por inicializar e orquestrar todos os componentes.
-   `config.py`: Arquivo de configuração central. Permite ajustar facilmente parâmetros da simulação, como número de clientes, tabelas, probabilidades de operação e durações.
-   `utils.py`: Funções utilitárias, como o logger formatado.
-   `db_resources.py`: Define os recursos do sistema (a classe `Table`).
-   `db_system.py`: Contém a lógica principal do SGBD simulado (as classes `LockManager` e `ClientConnection`).
-   `snapshot.py`: Implementa o algoritmo de snapshot e a lógica de detecção de deadlock (as classes `DeadlockDetector` e `Snapshotter`).

## Como Executar

### Pré-requisitos

-   Python 3.x

### Passos

1.  Clone este repositório ou salve todos os arquivos (`.py` e `.md`) em uma única pasta.
2.  Abra um terminal e navegue até a pasta do projeto.
3.  Execute o arquivo principal:

    ```bash
    python main.py
    ```

4.  Observe a saída no terminal. Você verá os logs das operações dos clientes, as análises de snapshot e, eventualmente, a mensagem de detecção de deadlock.

    ```
    [DBA-Monitor] !!! DEADLOCK DETECTED !!!
    [DBA-Monitor] Dependency cycle found: Client-X -> Client-Y -> Client-X
    [DBA-Monitor] Initiating graceful shutdown of the application...
    ```

5.  A aplicação irá encerrar automaticamente após detectar o primeiro deadlock. Você também pode encerrá-la a qualquer momento pressionando `Ctrl+C`.

## Configuração

Para experimentar diferentes cenários, edite o arquivo `config.py`. Você pode, por exemplo:
-   Aumentar `NUM_TABLES` para diminuir a chance de deadlocks.
-   Diminuir `NUM_TABLES` para aumentar a contenção e a chance de deadlocks.
-   Ajustar `WRITE_PROBABILITY` para alterar a frequência de operações de escrita.
-   Modificar os `_RANGE` para alterar a duração das operações.
