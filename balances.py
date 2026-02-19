""" 
Este archivo implementa la gestión del estado económico del sistema 
mediante la clase BalanceManager. Dado que la arquitectura implementada sigue un modelo de cuentas, 
el estado del sistema se define como un conjunto de balances asociados a identificadores de cuenta (bancos/nodos), 
que en este caso representan a las distintas entidades bancarias participantes en la red. 
BalanceManager es el componente responsable de almacenar dichos saldos, permitir su consulta, 
validar si una transacción es aplicable desde el punto de vista económico (formato básico y 
fondos suficientes) y, finalmente, aplicar transacciones y bloques actualizando el estado.
Gracias a este archivo ejecutamos un sistema funcional en el que los bloques acordados por 
consenso tienen un efecto concreto sobre el estado. 
"""

from __future__ import annotations

from typing import Dict

from transaction import Transaction
from block import Block


class BalanceManager:
    """
    Gestiona los balances de los bancos/nodos, permite su consulta y validar si una 
    transacción es aplicable desde el punto de vista económico.  
    """

    def __init__(self, initial_balances: Dict[str, int]) -> None:
        # initial_balances es un diccionario con los balances iniciales
        self.balances: Dict[str, int] = initial_balances.copy() #utilizamos copy() para evitar compartir referencia scon el diccionario original leído del bloque génesis
        
        
    def get_balance(self, account: str) -> int:
        """ 
        Obtiene y establece balances
        """
        return self.balances.get(account, 0) #Si la cuenta no existe devuelve 0 (las cuentas desconocidas existen, pero con saldo 0)

    def set_balance(self, account: str, value: int) -> None:
        """ 
        Permite establecer el saldo de una cuenta 
        """
        self.balances[account] = value


    def has_funds(self, account: str, amount: int) -> bool:
        """ 
        Realiza una validación económica para comprobar si una trnasacción es aplicable económicamente
        """
        return self.get_balance(account) >= amount

    def is_valid_transaction(self, tx: Transaction) -> bool:
        """
        Validación económica (NO incluye verificación criptográfica).
        """
        # Validación de formato
        if not tx.is_well_formed(): 
            return False

        # Comprobación de que tiene fondos suficientes
        if not self.has_funds(tx.sender, tx.amount):
            return False

        return True

    def apply_transaction(self, tx: Transaction) -> bool: #Esto solo se ejecuta cuando a un bloque se le aplica commit en apply_block
        """
        Aplica una transacción si es económicamente válida.
        Asume que la firma ya ha sido verificada fuera de aquí (Blockchain.validate_transactions)
        """
        if not self.is_valid_transaction(tx):
            return False

        self.balances[tx.sender] -= tx.amount
        self.balances[tx.receiver] += tx.amount
        return True

    def apply_block(self, block: Block) -> None:
        """
        Aplica todas las transacciones de un bloque ya validado por consenso.
        """
        for tx in block.transactions:
            self.apply_transaction(tx)

    # No sé si los voy a querer, porque no se si me interesa hacer un depósito y sacar dinero del banco 
    def deposit(self, account: str, amount: int) -> None:
        self.balances[account] = self.get_balance(account) + amount

    def withdraw(self, account: str, amount: int) -> bool:
        if self.has_funds(account, amount):
            self.balances[account] -= amount
            return True
        return False

    def snapshot(self) -> Dict[str, int]:
        """
        Devuelve una copia del estado actual de los balances.
        """
        return self.balances.copy()

    def can_apply_transaction(self, tx: Transaction) -> bool:
        """ 
        Comprueba la estructura y los fondos de las transacciones
        """
        if not tx.is_well_formed():
            return False
        if not self.has_funds(tx.sender, tx.amount):
            return False
        return True

    def __repr__(self) -> str:
        return f"BalanceManager({self.balances})"
