from json import dumps
from passlib.hash import pbkdf2_sha256

def get_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": dumps(body)
    }

def validate_cnpj(cnpj):
    # Remove any non-digit characters
    cnpj = ''.join(filter(str.isdigit, cnpj))
    
    if len(cnpj) != 14:
        return False
    
    # Check if all digits are the same
    if cnpj == cnpj[0] * 14:
        return False
    
    # First digit validation
    sum = 0
    weight = 5
    for i in range(12):
        sum += int(cnpj[i]) * weight
        weight = weight - 1 if weight > 2 else 9
    
    digit = 11 - (sum % 11)
    if digit > 9:
        digit = 0
    
    if digit != int(cnpj[12]):
        return False
    
    # Second digit validation
    sum = 0
    weight = 6
    for i in range(13):
        sum += int(cnpj[i]) * weight
        weight = weight - 1 if weight > 2 else 9
    
    digit = 11 - (sum % 11)
    if digit > 9:
        digit = 0
    
    return digit == int(cnpj[13])


def validate_cpf(cpf):
    # Remove any non-digit characters
    cpf = ''.join(filter(str.isdigit, cpf))
    
    if len(cpf) != 11:
        return False
    
    # Check if all digits are the same
    if cpf == cpf[0] * 11:
        return False
    
    # First digit validation
    sum = 0
    for i in range(9):
        sum += int(cpf[i]) * (10 - i)
    
    digit = 11 - (sum % 11)
    if digit > 9:
        digit = 0
    
    if digit != int(cpf[9]):
        return False
    
    # Second digit validation
    sum = 0
    for i in range(10):
        sum += int(cpf[i]) * (11 - i)
    
    digit = 11 - (sum % 11)
    if digit > 9:
        digit = 0
    
    return digit == int(cpf[10])


def verify_password(stored_password, provided_password):
    return pbkdf2_sha256.verify(provided_password, stored_password)