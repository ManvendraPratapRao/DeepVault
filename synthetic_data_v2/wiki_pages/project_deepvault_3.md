# Project DeepVault: Secure Multi-Party Computation (SMPC) using Homomorphic Encryption
=====================================================================

## Introduction
---------------

In Project DeepVault, we are exploring ways to securely store and process sensitive information while maintaining data privacy. One promising approach is the use of Secure Multi-Party Computation (SMPC) techniques. In this document, we will focus on the implementation of a Homomorphic Encryption (HE) based SMPC component.

The inspiration for this component came from our work on Project Chimera, where we investigated the use of HE for privacy-preserving machine learning. Emily, our Principal ML Engineer, previously worked on a related issue (see [Chimera HE Implementation](https://omnisynapse.gitlab.io/project-chimera/-/wikis/homomorphic-encryption-implementation)) and provided valuable insights that informed the design of this component.

## Technical Details
-------------------

Homomorphic Encryption (HE) is a type of encryption that allows computations to be performed directly on ciphertexts without decrypting them first. In our SMPC component, we use a HE library to perform arithmetic operations on encrypted data. This enables multiple parties to collaborate on a computation while keeping their inputs private.

We have chosen to use the [FHEW](https://fhe-w.org/) library, which provides an efficient and secure implementation of HE. Our component uses the Paillier scheme, which is a widely used and well-studied HE scheme.

### Encryption and Decryption

Encryption is performed using the following formula:
`c = E(m; r) = (m^r \* g^r) mod N^2`

where `c` is the ciphertext, `m` is the plaintext, `r` is a random number, and `g` is a generator element.

Decryption is performed using the following formula:
`m = D(c; \lambda) = L(c^λ mod N^2)`

where `m` is the decrypted plaintext, `c` is the ciphertext, and `λ` is a secret key.

### Arithmetic Operations

Our component supports various arithmetic operations, including addition, multiplication, and exponentiation. These operations are performed directly on the encrypted data using the HE library.

## How-to Use the Component
---------------------------

To use the SMPC component, follow these steps:

1.  Import the component into your project using the following code:
    ```python
from deepvault.smpc import HEComponent
```
2.  Create an instance of the component using the following code:
    ```python
component = HEComponent()
```
3.  Encrypt your data using the `encrypt` method:
    ```python
ciphertext = component.encrypt(plaintext)
```
4.  Perform arithmetic operations on the encrypted data using the `add`, `multiply`, and `exponentiate` methods:
    ```python
result = component.add(ciphertext1, ciphertext2)
result = component.multiply(ciphertext1, ciphertext2)
result = component.exponentiate(ciphertext, exponent)
```
5.  Decrypt the result using the `decrypt` method:
    ```python
decrypted_result = component.decrypt(result)
```

## Limitations/Gotchas
-------------------------

While our SMPC component is a powerful tool for secure collaboration, there are some limitations and gotchas to be aware of:

*   **Performance**: HE operations can be computationally expensive, making this component less suitable for large-scale computations.
*   **Key management**: The secret key used for decryption must be managed securely to prevent unauthorized access to sensitive data.
*   **Ciphertext size**: The size of the ciphertext can be larger than the plaintext, which can impact storage and communication costs.

By understanding these limitations and using the SMPC component judiciously, we can ensure secure and private collaboration in Project DeepVault.