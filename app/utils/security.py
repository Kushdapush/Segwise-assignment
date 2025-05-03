import hmac
import hashlib

def generate_signature(secret: str, payload: str) -> str:
    """
    Generate a signature for the webhook payload.
    
    Args:
        secret: The subscription secret
        payload: The JSON payload as a string
        
    Returns:
        Hex-encoded HMAC signature
    """
    signature = hmac.new(
        key=secret.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return signature

def verify_signature(payload: str, secret: str, signature: str) -> bool:
    """
    Verify that a signature matches the expected value.
    
    Args:
        payload: The raw payload as a string
        secret: The subscription secret
        signature: The provided signature to verify
        
    Returns:
        Boolean indicating if signature is valid
    """
    expected_signature = generate_signature(secret, payload)
    return hmac.compare_digest(expected_signature, signature)