"""
Exercise Donation Bot - Blink Lightning API
Blink GraphQL API를 사용한 Lightning 결제 처리 (CitadelPay 방식)
"""
import aiohttp
import asyncio
import logging
import qrcode
from io import BytesIO
from typing import Optional, Dict, Any
import config

logger = logging.getLogger(__name__)


class BlinkPayment:
    """Blink GraphQL API를 사용한 Lightning 결제 처리"""
    
    def __init__(self):
        self.api_endpoint = config.BLINK_API_ENDPOINT
        self.api_key = config.BLINK_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.api_key
        }
        self.btc_wallet_id = None  # 캐시
        self.max_retries = config.MAX_RETRIES
        self.retry_delay = config.RETRY_DELAY
    
    async def _graphql_request(self, query: str, variables: dict = None, retries: int = None) -> Dict[str, Any]:
        """GraphQL 요청 실행 (재시도 로직 포함)"""
        if retries is None:
            retries = self.max_retries
        
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        last_error = None
        
        for attempt in range(retries):
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        self.api_endpoint,
                        json=payload,
                        headers=self.headers
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if "errors" in data:
                                raise Exception(f"GraphQL Error: {data['errors']}")
                            return data.get("data")
                        else:
                            text = await response.text()
                            raise Exception(f"HTTP {response.status}: {text}")
                            
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    logger.warning(f"GraphQL request failed (attempt {attempt + 1}/{retries}): {e}")
                    await asyncio.sleep(self.retry_delay * (attempt + 1))  # 점진적 대기
                else:
                    logger.error(f"GraphQL request failed after {retries} attempts: {e}")
        
        raise last_error
    
    async def get_btc_wallet_id(self) -> str:
        """BTC 지갑 ID 가져오기 (캐시)"""
        if self.btc_wallet_id:
            return self.btc_wallet_id
        
        query = """
        query Me {
          me {
            defaultAccount {
              wallets {
                id
                walletCurrency
                balance
              }
            }
          }
        }
        """
        
        result = await self._graphql_request(query)
        
        if not result or "me" not in result:
            raise Exception("Failed to get wallet information")
        
        wallets = result["me"]["defaultAccount"]["wallets"]
        
        # BTC 지갑 찾기
        for wallet in wallets:
            if wallet.get("walletCurrency") == "BTC":
                self.btc_wallet_id = wallet["id"]
                logger.info(f"BTC wallet found: {self.btc_wallet_id[:8]}...")
                return self.btc_wallet_id
        
        raise Exception("BTC wallet not found")
    
    async def create_invoice(self, amount_sats: int, memo: str = None) -> Dict[str, Any]:
        """Lightning Invoice 생성"""
        wallet_id = await self.get_btc_wallet_id()
        
        mutation = """
        mutation LnInvoiceCreate($input: LnInvoiceCreateInput!) {
          lnInvoiceCreate(input: $input) {
            invoice {
              paymentRequest
              paymentHash
              satoshis
            }
            errors {
              message
            }
          }
        }
        """
        
        variables = {
            "input": {
                "walletId": wallet_id,
                "amount": amount_sats,
                "memo": memo or "운동 기부"
            }
        }
        
        result = await self._graphql_request(mutation, variables)
        
        if result and "lnInvoiceCreate" in result:
            payload = result["lnInvoiceCreate"]
            
            if payload.get("errors") and len(payload["errors"]) > 0:
                error_msg = payload["errors"][0].get("message") or "lnInvoiceCreate 오류"
                logger.error(f"Invoice creation error: {error_msg}")
                raise Exception(error_msg)
            
            invoice = payload.get("invoice")
            
            if not invoice or not invoice.get("paymentRequest"):
                raise Exception("lnInvoiceCreate 응답에 paymentRequest 없음")
            
            logger.info(f"Invoice created: {amount_sats} sats")
            return {
                "invoice": invoice["paymentRequest"],
                "payment_hash": invoice["paymentHash"],
                "satoshis": invoice["satoshis"]
            }
        else:
            raise Exception("Invalid response from Blink API")
    
    async def get_invoice_status(self, payment_request: str) -> Optional[Dict[str, Any]]:
        """결제 상태 확인"""
        query = """
        query lnInvoicePaymentStatusByPaymentRequest($input: LnInvoicePaymentStatusByPaymentRequestInput!) {
          lnInvoicePaymentStatusByPaymentRequest(input: $input) {
            paymentHash
            paymentPreimage
            paymentRequest
            status
          }
        }
        """
        
        variables = {
            "input": {
                "paymentRequest": payment_request
            }
        }
        
        result = await self._graphql_request(query, variables, retries=1)  # 상태 확인은 재시도 불필요
        return result.get("lnInvoicePaymentStatusByPaymentRequest")
    
    async def check_payment(self, payment_request: str, max_attempts: int = None, interval: int = None) -> bool:
        """결제 완료 확인 - 폴링"""
        if max_attempts is None:
            max_attempts = config.PAYMENT_TIMEOUT // config.PAYMENT_CHECK_INTERVAL
        if interval is None:
            interval = config.PAYMENT_CHECK_INTERVAL
        
        logger.info(f"Checking payment (max {max_attempts} attempts, {interval}s interval)")
        
        for attempt in range(max_attempts):
            try:
                status_obj = await self.get_invoice_status(payment_request)
                
                if not status_obj:
                    logger.warning(f"⚠️ 상태 조회 결과 없음 (attempt {attempt + 1})")
                else:
                    status = status_obj.get("status")
                    logger.debug(f"🔍 Blink invoice status: {status}")
                    
                    if status == "PAID":
                        logger.info("✅ Payment confirmed: PAID")
                        return True
                    elif status == "EXPIRED":
                        logger.warning("❌ Invoice expired")
                        return False
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.warning(f"Payment check error (attempt {attempt + 1}): {e}")
                await asyncio.sleep(interval)
        
        logger.warning(f"Payment check timeout after {max_attempts} attempts")
        return False
    
    async def get_lnurl_invoice_from_address(self, lightning_address: str, amount_sats: int) -> str:
        """Lightning Address에서 Invoice 요청"""
        parts = lightning_address.split("@")
        if len(parts) != 2:
            raise Exception("Invalid Lightning Address format")
        
        username, domain = parts
        lnurl_url = f"https://{domain}/.well-known/lnurlp/{username}"
        
        logger.info(f"Requesting invoice from {lightning_address} for {amount_sats} sats")
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # LNURL 정보 가져오기
            async with session.get(lnurl_url) as response:
                if response.status != 200:
                    raise Exception(f"LNURL request failed: {response.status}")
                
                data = await response.json()
                
                if data.get("status") == "ERROR":
                    raise Exception(data.get("reason") or "LNURL error")
                
                callback_url = data.get("callback")
                if not callback_url:
                    raise Exception("No callback URL in LNURL response")
            
            # Invoice 요청
            amount_msat = amount_sats * 1000
            
            async with session.get(
                callback_url,
                params={"amount": amount_msat}
            ) as response:
                if response.status != 200:
                    raise Exception(f"Invoice request failed: {response.status}")
                
                invoice_data = await response.json()
                
                if invoice_data.get("status") == "ERROR":
                    raise Exception(invoice_data.get("reason") or "Invoice request error")
                
                invoice = invoice_data.get("pr")
                if not invoice:
                    raise Exception("No invoice in response")
                
                logger.info(f"Invoice received from {lightning_address}")
                return invoice
    
    async def probe_invoice_fee(self, payment_request: str) -> int:
        """Invoice 수수료 예측"""
        wallet_id = await self.get_btc_wallet_id()
        
        mutation = """
        mutation LnInvoiceFeeProbe($input: LnInvoiceFeeProbeInput!) {
          lnInvoiceFeeProbe(input: $input) {
            amount
            errors {
              message
            }
          }
        }
        """
        
        variables = {
            "input": {
                "walletId": wallet_id,
                "paymentRequest": payment_request
            }
        }
        
        try:
            result = await self._graphql_request(mutation, variables, retries=1)
            
            if result and "lnInvoiceFeeProbe" in result:
                payload = result["lnInvoiceFeeProbe"]
                
                if payload.get("errors"):
                    logger.warning(f"Fee probe returned errors: {payload['errors']}")
                    return 0
                
                fee = payload.get("amount", 0)
                logger.debug(f"Fee probe result: {fee} sats")
                return fee
            
            return 0
            
        except Exception as e:
            logger.warning(f"Fee probe error: {e}")
            return 0
    
    async def pay_invoice(self, payment_request: str) -> str:
        """Invoice 결제"""
        wallet_id = await self.get_btc_wallet_id()
        
        mutation = """
        mutation LnInvoicePaymentSend($input: LnInvoicePaymentInput!) {
          lnInvoicePaymentSend(input: $input) {
            status
            errors {
              message
              path
              code
            }
          }
        }
        """
        
        variables = {
            "input": {
                "walletId": wallet_id,
                "paymentRequest": payment_request
            }
        }
        
        logger.info("Sending payment...")
        result = await self._graphql_request(mutation, variables)
        
        if result and "lnInvoicePaymentSend" in result:
            payload = result["lnInvoicePaymentSend"]
            
            if payload.get("errors") and len(payload["errors"]) > 0:
                error = payload["errors"][0]
                error_msg = error.get("message") or "Payment failed"
                logger.error(f"Payment error: {error_msg}")
                raise Exception(error_msg)
            
            status = payload.get("status")
            logger.info(f"Payment result: {status}")
            return status
        else:
            raise Exception("Invalid payment response")
    
    def generate_qr_code(self, invoice: str) -> BytesIO:
        """Invoice QR 코드 생성"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(invoice.upper())
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer


# ==================== 헬퍼 함수 ====================

async def create_lightning_payment(amount_sats: int, comment: str = None) -> tuple:
    """Lightning 결제 생성"""
    blink = BlinkPayment()
    
    result = await blink.create_invoice(amount_sats, comment)
    invoice = result['invoice']
    payment_hash = result['payment_hash']
    
    qr_buffer = blink.generate_qr_code(invoice)
    
    return invoice, qr_buffer, payment_hash


async def verify_payment(payment_request: str, timeout: int = None) -> bool:
    """결제 확인"""
    if timeout is None:
        timeout = config.PAYMENT_TIMEOUT
    
    blink = BlinkPayment()
    max_attempts = timeout // config.PAYMENT_CHECK_INTERVAL
    
    return await blink.check_payment(payment_request, max_attempts, interval=config.PAYMENT_CHECK_INTERVAL)


async def send_to_lightning_address(destination: str, amount_sats: int, memo: str = None) -> Dict[str, Any]:
    """
    Lightning Address로 전송 (CitadelPay 방식)
    
    Returns:
        dict: {'status': 'SUCCESS', 'fee': ..., 'invoice': ...}
    """
    blink = BlinkPayment()
    
    logger.info(f"Sending {amount_sats} sats to {destination}")
    
    # 1. Lightning Address → Invoice
    invoice = await blink.get_lnurl_invoice_from_address(destination, amount_sats)
    
    # 2. 수수료 확인
    fee = await blink.probe_invoice_fee(invoice)
    logger.info(f"Transfer fee: {fee} sats {'(FREE - Blink internal)' if fee == 0 else ''}")
    
    # 3. 결제 실행
    status = await blink.pay_invoice(invoice)
    
    logger.info(f"Transfer complete: {status}")
    
    return {
        "status": status,
        "fee": fee,
        "invoice": invoice
    }
