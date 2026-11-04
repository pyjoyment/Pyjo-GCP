from Pyjo.Util import b64_encode

import re


# A key of RSA of 2048 bits made for the tests, of its numbers, whose PEM the tests make, and the signature of RS256 of
# b'header.payload' of the package cryptography, as the padding of PKCS #1 v1.5 makes the signature of a key and a
# message the same everywhere; no PEM of a private key is in the repository, which a scanner of secrets would take
N = int(
    'cec328998489952186578056c04ea390a70a2fb573f4bd6b231a8fb4c61432ff173266bb744d42db925a5ad18813e47558254822'
    '6ebc367a0cb47195d6e88f0c8dd62f9e66ee590e135662471e0d9e30b58a4e3a0b6cb7752a735e4f8f9c10929d02f24b8022ef28'
    '52f31d9ba0604fb1b18c2e562cce47290ab16ca630234a2608045aa8060a76b77ae518e3caf2ae639dfe3fa3b479d87e320207cb'
    '48a7575a481017559075422d39d5650af4b28a07d07c544a2f31bf3f843898d34999e1701e43498f8a1a6be19b5b751503a8b14a'
    '15e7ba48e728bfa91c86d05fe2ef4fb06ed8a0402b55a2de66c4d3211c4a2d558e57f3f56eb083ebd861ae2021a58cef',
    16,
)
E = 0x10001
D = int(
    '1127efc35fa10f457327b62156389d02cd5e391bcc2d9dd65f7298102ecbc4df164fc19a42dd191a2dfeb84d6d863506c260b65a'
    'a7748f85d2d4a68481713c52fba57b8ca0186a3ddf72b066b5429368c50f78b2ce12e029b1f3221518ef8775b478806ae0bfdeea'
    '76f055dfe3cfb069f5042c2e19bb7461eb1e524b7b700d608c137d88e12a9065fce38d06af0cc6d2d5bcc6889323da5e09cd1507'
    '09c93ea82be0699185389603c8fcb71549a842e82ea3961469bb759f20e039c07fa371897ee131c55778657e354dd4a912bb4693'
    '89553032dcc8de72d27273a6eea840fa6cc87bcfc93d6606bcf0b427dc360af56a2e75f02c74fb6099e7fb2d3cd87b55',
    16,
)
P = int(
    'eda9654af9224f13f0c61af7c1cb976d79194f531b92b56073476e0fc0be645303abbd0b50def1e74ef7bd0726451e4908e51cbe'
    'd1e532754b2905c4dd825710a5eb3284f3b83d6278094ea4c06e904b5ec74e76913646a2100a9f34becd162a57ed54c616dbe767'
    'ec6070fcac72b2702c76083f6aa54ae3459a35552793bc3b',
    16,
)
Q = int(
    'deb765f91b1cd5edf6d3219d39ac0f56d52b3d7c5c7e0bfe0cb13174becb0a0ec507d95702eecfda6724f71970e81aef7e25b90d'
    'a171bbc997992b765727a325d0695896f4797a2027d307a1937db521b03bc0aa860418c9d81bc611b0ddc71d126d7550ccea1c82'
    'a3c08363ca3abaad8d46474fd23f7532dd07a4afc3e94add',
    16,
)
SIGNATURE = bytes.fromhex(
    'cb000be2979615acf9b7829c9e1a4529aec7c384c5cf6f6510544bcb15e2545d8d896c89fcbddf75d04a30e0efda224691b18bb6'
    '82276bc4dd182a357acd74003bc2be71935514bba0b8e47c486d930fb8217b5b2f04b9b6450fa5958a75db3ae5e58aaa7c33d536'
    'a5778059dcedc7f0cb2c23ee5c15105ee74739ef7ea555c87d84402466190d1b94fca559c82a7a09b19f27f95b99bde392011246'
    '366e26394560820e88685c63f22f53881083e1c699ebf7f602f0fb03eeb4f1e2940300d9bb5e96c5516062360be392b9207a0045'
    '9612f2310f41accec5b29b6017982b2359a8236d6ee0240d3cc024e0744ae76c1e11862c73a2530790f809f4b6ec587a'
)


def der_length(length):
    if length < 0x80:
        return bytes([length])
    data = length.to_bytes((length.bit_length() + 7) // 8)
    return bytes([0x80 | len(data)]) + data


def tlv(tag, content):
    return bytes([tag]) + der_length(len(content)) + content


def integer(value):
    return tlv(0x02, value.to_bytes(value.bit_length() // 8 + 1))


def sequence(*items):
    return tlv(0x30, b''.join(items))


def pem(label, der):
    lines = re.findall('.{1,64}', b64_encode(der, ''))
    return '\n'.join([f'-----BEGIN {label}-----', *lines, f'-----END {label}-----']) + '\n'


RSA_ENCRYPTION = sequence(tlv(0x06, bytes.fromhex('2a864886f70d010101')), tlv(0x05, b''))
PKCS1 = sequence(
    integer(0), *(integer(v) for v in (N, E, D, P, Q, D % (P - 1), D % (Q - 1), pow(Q, -1, P)))
)  # fmt: skip
PKCS8 = sequence(integer(0), RSA_ENCRYPTION, tlv(0x04, PKCS1))
PUBLIC = sequence(RSA_ENCRYPTION, tlv(0x03, b'\x00' + sequence(integer(N), integer(E))))


if __name__ == '__main__':
    from Pyjo.Test import plan

    plan(skip_all='helper module, not a test')
