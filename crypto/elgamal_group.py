"""Fixed 2048-bit safe-prime group for ElGamal (p = 2q + 1 with q prime, generator g = 2).

Generated once with `openssl dhparam -2 2048`; primality of p and q is re-checked by the test suite.
Sharing a group means each user only generates a private exponent, which takes microseconds.
"""

P = int(
    "c95b39d7d570378d9dad95be99fcbd7dc23d3d342740f1fc5d5b0e43bc10b403"
    "b180b96c97b079ca8e795e6a2bc14f780a086bd968fb11c894d0c582a5b9f285"
    "ecf1e407d082898738a49a8c4032b37c22d0f163bb02171239acee65c34b614c"
    "1bdc28fff5d762089ba8da474fafdb40ac0a520a245909400ef29eb59b989996"
    "03fdfd52b07a1bc12e4991f3e006b397f9434c1e3fad6edb0d505f380854e7f2"
    "b735ce7680d5c32fac1e8f85edee12de0830b9eac80462a5c8fe6e218bd342a8"
    "ac659579452decc9adadc21678034b981d0b6c46052762d9499b1bdd7f57cc8e"
    "fc4c785dd76541ef2e0831de70e43f7d1af0117d1bd7f1c4a9f7c2af902bf48f",
    16,
)
G = 2
