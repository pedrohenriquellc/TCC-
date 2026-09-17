# 📸 Evidências dos testes TLS/PQC

Coloque aqui os **prints** dos testes de conformidade, com **exatamente estes nomes**
(o `README.md` principal já os referencia):

| Arquivo | Teste | O que capturar |
|---|---|---|
| `ssl-org-ip.png` | [SSL.org](https://www.ssl.org/) com o IP `144.22.166.21` | tabela com **Certificate Trusted: Yes** e **Good signature · Good key** |
| `digicert-pqc-ip.png` | [DigiCert PQC](https://www.digicert.com/pqc-checker) com o IP `144.22.166.21` | resultado **Pass** (TLS 1.3 + Quantum-safe key exchange) |
| `ssllabs.png` | [Qualys SSL Labs](https://www.ssllabs.com/ssltest/analyze.html?d=144-22-166-21.sslip.io) com o hostname | nota **A+** + suporte a **PQC** |

**Como tirar o print no Windows:** `Win + Shift + S` (recorte), cole no Paint e salve
com o nome acima nesta pasta.

> Recapture perto da apresentação: o certificado de IP renova sozinho, e os
> resultados se mantêm.
