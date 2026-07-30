import asyncio, logging, random, string, hashlib, time

logger = logging.getLogger(__name__)


class CaptchaVerifier:
    def __init__(self):
        self.pending = {}

    def generate(self, length=4):
        code = ''.join(random.choices(string.digits, k=length))
        return code

    def generate_math(self):
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        op = random.choice(['+', '-', '*'])
        if op == '+':
            answer = a + b
        elif op == '-':
            a, b = max(a, b), min(a, b)
            answer = a - b
        else:
            a, b = min(a, 10), min(b, 10)
            answer = a * b
        return f"{a} {op} {b}", str(answer)

    def create_challenge(self, user_id, challenge_type='math'):
        if challenge_type == 'math':
            question, answer = self.generate_math()
        else:
            answer = self.generate(4)
            question = f"Введите код: {answer}"

        challenge_id = hashlib.md5(f"{user_id}{time.time()}{random.random()}".encode()).hexdigest()[:8]
        self.pending[challenge_id] = {
            "user_id": user_id,
            "answer": answer,
            "attempts": 0,
            "max_attempts": 3,
            "created_at": time.time(),
            "solved": False
        }

        return challenge_id, question

    def verify(self, challenge_id, user_answer):
        challenge = self.pending.get(challenge_id)
        if not challenge:
            return False, "Challenge not found"

        if time.time() - challenge['created_at'] > 300:
            self.pending.pop(challenge_id, None)
            return False, "Challenge expired"

        challenge['attempts'] += 1
        if challenge['attempts'] > challenge['max_attempts']:
            self.pending.pop(challenge_id, None)
            return False, "Too many attempts"

        if user_answer.strip() == challenge['answer'].strip():
            challenge['solved'] = True
            self.pending.pop(challenge_id, None)
            return True, "Solved"

        return False, "Wrong answer"

    def cleanup(self):
        now = time.time()
        expired = [k for k, v in self.pending.items() if now - v['created_at'] > 300]
        for k in expired:
            self.pending.pop(k, None)
