class PaymentsService:
    async def create_invoice(self, amount: int) -> dict:
        return {"amount": amount, "status": "stub"}
