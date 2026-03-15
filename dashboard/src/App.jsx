import { useState, useEffect } from 'react'
import { isConnected, setAllowed, getUserInfo, signTransaction, getNetwork } from '@stellar/freighter-api'
import * as StellarSdk from 'stellar-sdk'
import './App.css'

// Use localhost for development, production URL for deployed version
const BACKEND_URL = import.meta.env.DEV ? 'http://localhost:8000' : 'https://payzee-production.up.railway.app'
const API_KEY = 'sk_stellar_pay_dev_b03352ef1d68164c675023b82538ea3d1d1902f69bc408b7'
const ESCROW_CONTRACT = 'CDSWWCK54G7N5U5DBYBBP3S4FFPGFOCJXDDOJLQ4HNSDPL2NC67CWQZ3'
const USDC_CONTRACT = 'CAQCFVLOBK5GIULPNZRGATJJMIZL5BSP7X5YJVMGCPTUEPFM4LVDSYQV'
const NETWORK_PASSPHRASE = StellarSdk.Networks.TESTNET

function App() {
  const [walletConnected, setWalletConnected] = useState(false)
  const [publicKey, setPublicKey] = useState(null)
  const [amount, setAmount] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [processing, setProcessing] = useState(false)
  const [card, setCard] = useState(null)
  const [testingPayment, setTestingPayment] = useState(false)
  const [paymentResult, setPaymentResult] = useState(null)
  const [merchantName, setMerchantName] = useState('')
  const [merchantDomain, setMerchantDomain] = useState('')
  const [originalAmount, setOriginalAmount] = useState('')

  // Get amount and merchant data from URL params (sent by extension)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const amountParam = params.get('amount')
    const merchantParam = params.get('merchant')
    const domainParam = params.get('domain')
    const originalAmountParam = params.get('originalAmount')
    
    if (amountParam) {
      setAmount(amountParam)
    }
    
    if (originalAmountParam) {
      setOriginalAmount(originalAmountParam)
      setStatus(`Converted ${originalAmountParam} to $${parseFloat(amountParam).toFixed(2)} USD`)
    } else if (merchantParam) {
      setStatus(`Payment for ${merchantParam}`)
    }
    
    if (merchantParam) {
      setMerchantName(merchantParam)
    }
    
    if (domainParam) {
      setMerchantDomain(domainParam)
    }
  }, [])

  // Check if Freighter is installed and listen for messages
  useEffect(() => {
    checkFreighterInstalled()
    
    // Listen for confirm transaction message from extension
    const handleMessage = (event) => {
      console.log('Dashboard: Message received from:', event.origin);
      console.log('Dashboard: Message data:', event.data);
      
      if (event.data.type === 'STELLAR_PAY_CONFIRM_TRANSACTION') {
        console.log('Dashboard: Confirm transaction requested, card:', card);
        console.log('Dashboard: Testing payment state:', testingPayment);
        // Trigger test payment automatically
        if (card && !testingPayment) {
          console.log('Dashboard: Triggering payment...');
          handleTestPayment();
        } else if (!card) {
          console.error('Dashboard: No card available');
        } else if (testingPayment) {
          console.log('Dashboard: Payment already in progress');
        }
      }
    };
    
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [card, testingPayment])

  async function checkFreighterInstalled() {
    const installed = await isConnected()
    if (!installed) {
      setError('Freighter wallet is not installed. Please install from https://freighter.app')
    }
  }

  async function connectWallet() {
    try {
      setError('')
      setStatus('Connecting to Freighter...')

      // Check if Freighter is available
      const freighterInstalled = await isConnected()
      if (!freighterInstalled) {
        throw new Error('Freighter wallet is not installed. Please install from https://freighter.app')
      }

      // Request permission (opens Freighter popup)
      await setAllowed()

      // Get user info
      const userInfo = await getUserInfo()
      
      if (!userInfo || !userInfo.publicKey) {
        throw new Error('Connection rejected or no account available. Please approve the connection in Freighter.')
      }

      // Check network
      const network = await getNetwork()
      if (network !== 'TESTNET') {
        throw new Error('Please switch Freighter to TESTNET network')
      }

      setPublicKey(userInfo.publicKey)
      setWalletConnected(true)
      setStatus(`Wallet connected: ${userInfo.publicKey.slice(0, 4)}...${userInfo.publicKey.slice(-4)}`)
      
    } catch (err) {
      console.error('Wallet connection error:', err)
      setError(err.message || 'Failed to connect wallet')
      setStatus('')
    }
  }

  async function handlePayment() {
    if (!amount || parseFloat(amount) <= 0) {
      setError('Please enter a valid amount')
      return
    }

    setProcessing(true)
    setError('')
    setCard(null)

    try {
      // Step 1: Initiate payment session
      setStatus('Creating payment session...')
      const sessionResponse = await fetch(`${BACKEND_URL}/api/v1/payment/initiate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY
        },
        body: JSON.stringify({
          amount: parseFloat(amount),
          user_public_key: publicKey,
          merchant_name: merchantName || 'Payzee Merchant'
        })
      })

      if (!sessionResponse.ok) {
        throw new Error('Failed to create payment session')
      }

      const session = await sessionResponse.json()
      console.log('Session created:', session)

      // Step 2: Build Soroban transaction
      setStatus('Building transaction...')
      const server = new StellarSdk.SorobanRpc.Server('https://soroban-testnet.stellar.org')
      const sourceAccount = await server.getAccount(publicKey)

      const contract = new StellarSdk.Contract(ESCROW_CONTRACT)

      // Convert USD to USDC stroops (7 decimals)
      const amountStroops = Math.floor(session.amount_usdc * 10000000)

      // Note: Soroban transactions don't support text memos - merchant data stored in backend
      const builtTransaction = new StellarSdk.TransactionBuilder(sourceAccount, {
        fee: '100000', // Higher fee for Soroban
        networkPassphrase: NETWORK_PASSPHRASE
      })
        .addOperation(
          contract.call(
            'deposit',
            StellarSdk.Address.fromString(publicKey).toScVal(), // user address
            StellarSdk.nativeToScVal(amountStroops, { type: 'i128' }), // amount
            StellarSdk.nativeToScVal(session.session_id, { type: 'string' }) // session_id
          )
        )
        .setTimeout(300)
        .build()

      // Prepare transaction for Soroban (adds resource footprint)
      const preparedTx = await server.prepareTransaction(builtTransaction)
      const xdr = preparedTx.toXDR()

      // Step 3: Sign with Freighter
      setStatus('Please sign the transaction in Freighter...')
      const signedXdr = await signTransaction(xdr, {
        networkPassphrase: NETWORK_PASSPHRASE
      })

      // Step 4: Submit transaction and get card immediately
      setStatus('Submitting transaction and creating virtual card...')
      const submitResponse = await fetch(`${BACKEND_URL}/api/v1/payment/submit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY
        },
        body: JSON.stringify({
          session_id: session.session_id,
          signed_xdr: signedXdr
        })
      })

      if (!submitResponse.ok) {
        const errorData = await submitResponse.json()
        throw new Error(errorData.detail || 'Failed to submit transaction')
      }

      const submitResult = await submitResponse.json()
      console.log('Transaction submitted:', submitResult)

      // Card is returned immediately in the response
      if (submitResult.card) {
        const cardData = {
          pan: submitResult.card.pan,
          cvv: submitResult.card.cvv,
          exp_month: submitResult.card.exp_month,
          exp_year: submitResult.card.exp_year,
          last_four: submitResult.card.last_four,
          token: submitResult.card.token,
          state: submitResult.card.state
        }
        
        setCard(cardData)
        setStatus('Virtual card created successfully')
        setProcessing(false)
        
        // Notify extension that card is ready
        if (window.opener) {
          window.opener.postMessage({
            type: 'STELLAR_PAY_CARD_READY',
            card: cardData
          }, '*')
        }
      } else {
        throw new Error('Card not returned in response')
      }

    } catch (err) {
      console.error('Payment error:', err)
      setError(err.message || 'Payment failed')
      setStatus('')
      setProcessing(false)
    }
  }

  async function handleTestPayment() {
    if (!card || !card.pan) {
      setError('No card available for testing')
      return
    }

    setTestingPayment(true)
    setPaymentResult(null)
    setError('')

    try {
      const amountCents = Math.floor(parseFloat(amount) * 100)
      
      const response = await fetch(`${BACKEND_URL}/api/v1/cards/test-payment`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY
        },
        body: JSON.stringify({
          pan: card.pan,
          amount_cents: amountCents
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Test payment failed')
      }

      const result = await response.json()
      setPaymentResult(result)
      setStatus('Test payment successful! ')
      
      // Send payment completion message to parent window (merchant page)
      setTimeout(() => {
        if (window.opener) {
          window.opener.postMessage({
            type: 'STELLAR_PAY_PAYMENT_COMPLETE',
            paymentDetails: {
              amount: amount,
              merchant: merchantName || 'Merchant',
              domain: merchantDomain || 'merchant.com',
              originalAmount: originalAmount || null
            }
          }, '*')
          console.log('Sent payment completion message to parent')
        }
        // Close dashboard after sending message
        setTimeout(() => window.close(), 500)
      }, 1500)
      
    } catch (err) {
      console.error('Test payment error:', err)
      setError(err.message || 'Test payment failed')
    } finally {
      setTestingPayment(false)
    }
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text)
    setStatus('Copied to clipboard!')
    setTimeout(() => setStatus('Virtual card created! '), 2000)
  }

  return (
    <div className="container">
      <div className="card">
        <div className="header">
          <h1>Payzee</h1>
          <p className="subtitle">Nothing But Crypto</p>
        </div>

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        {!walletConnected ? (
          <div className="connect-section">
            <p className="info-text">
              Connect your Freighter wallet to continue with the payment
            </p>
            <button onClick={connectWallet} className="btn-primary">
              Connect Freighter Wallet
            </button>
          </div>
        ) : !card ? (
          <div className="payment-section">
            {merchantName && (
              <div className="merchant-info" style={{background: 'white', border: '2px solid black', padding: '16px', borderRadius: '4px', marginBottom: '20px'}}>
                <div style={{fontSize: '12px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '8px'}}>Merchant</div>
                <div style={{fontSize: '18px', fontWeight: '700', marginBottom: '4px'}}>{merchantName}</div>
                {merchantDomain && <div style={{fontSize: '14px', color: '#666'}}>{merchantDomain}</div>}
                {originalAmount && (
                  <div style={{marginTop: '12px', padding: '8px', background: '#f9fafb', borderRadius: '4px'}}>
                    <div style={{fontSize: '11px', color: '#666', marginBottom: '4px'}}>Original Amount</div>
                    <div style={{fontSize: '14px', fontWeight: '600'}}>{originalAmount}</div>
                    <div style={{fontSize: '11px', color: '#666', marginTop: '4px'}}>Converted to ${parseFloat(amount).toFixed(2)} USD</div>
                  </div>
                )}
              </div>
            )}
            
            <div className="wallet-info">
              <span className="label">Connected Wallet</span>
              <span className="value">{publicKey.slice(0, 8)}...{publicKey.slice(-8)}</span>
            </div>

            <div className="form-group">
              <label htmlFor="amount">Payment Amount (USDC)</label>
              <div style={{position: 'relative'}}>
                <span style={{position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', fontSize: '16px', fontWeight: '600', color: '#666'}}>$</span>
                <input
                  id="amount"
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="10.00"
                  step="0.01"
                  min="1"
                  disabled={processing}
                  style={{paddingLeft: '28px'}}
                />
              </div>
              {originalAmount && (
                <div style={{fontSize: '12px', color: '#666', marginTop: '6px'}}>
                  Converted from {originalAmount}
                </div>
              )}
            </div>

            <button 
              onClick={handlePayment}
              disabled={processing || !amount}
              className="btn-primary"
            >
              {processing ? 'Processing...' : 'Pay USDC'}
            </button>

            {status && (
              <div className="status-message">
                {status}
              </div>
            )}
          </div>
        ) : (
          <div className="card-section">
            <h2>Virtual Card Ready</h2>
            <p className="card-instruction">
              Copy the details below and paste them in the merchant checkout page
            </p>

            <div className="card-display">
              <div className="card-field">
                <label>Card Number</label>
                <div className="card-value">
                  <code>{card.pan || 'N/A'}</code>
                  <button 
                    onClick={() => copyToClipboard(card.pan)}
                    className="btn-copy"
                  >
                    Copy
                  </button>
                </div>
              </div>

              <div className="card-row">
                <div className="card-field">
                  <label>Expiry Date</label>
                  <div className="card-value">
                    <code>
                      {card.exp_month}/{card.exp_year}
                    </code>
                  </div>
                </div>

                <div className="card-field">
                  <label>CVV</label>
                  <div className="card-value">
                    <code>{card.cvv || 'N/A'}</code>
                    <button 
                      onClick={() => copyToClipboard(card.cvv)}
                      className="btn-copy"
                    >
                      Copy
                    </button>
                  </div>
                </div>
              </div>

              <div className="card-field">
                <label>Card State</label>
                <div className="card-value">
                  <strong>{card.state || 'OPEN'}</strong>
                </div>
              </div>

              <div className="card-note">
                ℹ️ This is a single-use card. Any unused amount will be automatically refunded to your wallet.
              </div>

              <button
                onClick={handleTestPayment}
                disabled={testingPayment || card.state === 'CLOSED'}
                className="btn-primary"
                style={{ marginTop: '20px', width: '100%' }}
              >
                {testingPayment ? 'Payment in progress...' : 'Test Payment (Sandbox)'}
              </button>

              {testingPayment && (
                <div className="loading-modal">
                  <div className="loading-content">
                    <div className="spinner"></div>
                    <h3>Payment in progress</h3>
                    <p>Please wait...</p>
                  </div>
                </div>
              )}

              {testingPayment && (
                <div className="loading-modal">
                  <div className="loading-content">
                    <div className="spinner"></div>
                    <h3>Payment in progress</h3>
                    <p>Please wait...</p>
                  </div>
                </div>
              )}

              {paymentResult && (
                <div className="status-message" style={{ marginTop: '15px', background: '#10b981', color: 'white' }}>
                   {paymentResult.message}
                  <br />
                  <small>Status: {paymentResult.status}</small>
                </div>
              )}
            </div>

            <button 
              onClick={() => window.close()}
              className="btn-secondary"
            >
              Close Window
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
