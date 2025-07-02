# Simulação de Detecção de Deadlock com Snapshot Distribuído - INE5418

Este projeto é uma simulação em Python que demonstra a detecção de *deadlocks* (impasses) em um ambiente concorrente, modelado como um Sistema de Gerenciamento de Banco de Dados (SGBD) simplificado.

O algoritmo principal utilizado para a detecção é o **Snapshot Distribuído de Chandy-Lamport**, que permite capturar um estado global consistente do sistema sem interromper sua execução.

## Como Funciona

1. **Usuários e Tabelas**: A simulação cria múltiplos "usuários" (`User`), que são *threads*, competindo por um conjunto de "tabelas" (`Table`), que são os recursos do sistema.
2. **Operações**: Cada usuário realiza continuamente operações de leitura (`READ`) ou escrita (`WRITE`).
   - Leituras não bloqueiam os recursos.
   - Escritas requerem um *lock* exclusivo sobre a tabela.
3. **Contenção e Espera**: Ao tentar escrever em uma tabela que já está bloqueada, o usuário entra em espera, criando potencial para deadlock.
4. **Snapshot Global**: Uma thread especial (`DeadlockDetector`) inicia snapshots periódicos. O snapshot registra:
   - Quais *locks* cada usuário mantém.
   - Qual recurso cada usuário está esperando.
5. **Grafo de Espera (Wait-For Graph)**: O detector constrói um grafo de espera a partir do snapshot. Se um ciclo é encontrado, um deadlock é confirmado.
6. **Encerramento Limpo**: Quando um deadlock é detectado, a simulação é encerrada de forma ordenada.

## Estrutura do Projeto

Todo o código está contido em um único arquivo:

- `main.py`: Contém toda a lógica da simulação, incluindo:
  - Definições das classes `User`, `Table` e `DeadlockDetector`.
  - Implementação do algoritmo de snapshot distribuído.
  - Detecção de ciclos no grafo de espera.
  - Inicialização e controle da simulação.
  - Sistema de *logging* com cores para facilitar a leitura dos logs por thread.

## Como Executar

### Pré-requisitos

- Python 3.x instalado.

### Passos

1. Salve o conteúdo do código fornecido em um arquivo chamado `main.py`.
2. Abra um terminal e navegue até o diretório onde está o arquivo.
3. Execute a simulação com:

    ```bash
    python main.py
    ```

4. Acompanhe a execução no terminal. Você verá:
   - As ações dos usuários (leitura, tentativa de escrita, espera).
   - O início de snapshots.
   - O estado global registrado.
   - A construção do grafo de espera.
   - A detecção (ou não) de deadlocks.

    Exemplo de saída quando ocorre um deadlock:

    ```
    !!! DEADLOCK DETECTED! !!!
    ```

5. O programa encerrará automaticamente após detectar um deadlock. Você também pode encerrar manualmente com `Ctrl+C`.

## Parâmetros da Simulação

Alguns parâmetros estão definidos diretamente no código:

- `num_users = 4`: Número de usuários (threads) concorrentes.
- `num_tables = 4`: Número de tabelas disponíveis.
- `sleep` com `random.uniform(0.5, 1.5)`: Intervalo aleatório entre ações dos usuários.
- Intervalo entre snapshots: 10 segundos.

Para alterar o comportamento da simulação, edite diretamente o código-fonte no trecho da função `main()`.

## Observações

- O sistema de logs foi personalizado com cores para facilitar a distinção entre as ações de diferentes threads.
- O algoritmo segue uma versão simplificada do protocolo de snapshot distribuído, adequado para fins didáticos.
- A simulação termina após a primeira detecção de deadlock para preservar a análise do estado do sistema.
