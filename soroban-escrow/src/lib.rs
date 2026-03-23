#![no_std]

use soroban_sdk::{
    contract, contractimpl, contracttype, token, Address, Env, String, Symbol, Vec,
};

/// Event emitted when a user deposits USDC for a payment
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PaymentReceived {
    pub user: Address,
    pub amount: i128,
    pub session_id: String,
    pub timestamp: u64,
}

/// Deposit record stored in contract
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Deposit {
    pub user: Address,
    pub amount: i128,
    pub session_id: String,
    pub claimed: bool,
    pub timestamp: u64,
}

/// Storage keys
#[contracttype]
pub enum DataKey {
    Admin,
    UsdcToken,
    Deposit(String), // session_id -> Deposit
    DepositList,     // List of all session IDs
}

#[contract]
pub struct StellarPayEscrow;

#[contractimpl]
impl StellarPayEscrow {
    /// Initialize the contract with admin and USDC token address
    pub fn initialize(env: Env, admin: Address, usdc_token: Address) {
        // Ensure not already initialized
        if env.storage().instance().has(&DataKey::Admin) {
            panic!("Already initialized");
        }

        // Store admin address
        env.storage().instance().set(&DataKey::Admin, &admin);

        // Store USDC token address
        env.storage().instance().set(&DataKey::UsdcToken, &usdc_token);

        // Initialize empty deposit list
        let empty_list: Vec<String> = Vec::new(&env);
        env.storage()
            .instance()
            .set(&DataKey::DepositList, &empty_list);
    }

    /// Deposit USDC for a payment
    /// User sends USDC to escrow with a unique session_id
    pub fn deposit(env: Env, user: Address, amount: i128, session_id: String) {
        // Require user authentication
        user.require_auth();

        // Validate amount
        if amount <= 0 {
            panic!("Amount must be positive");
        }

        // Check if session_id already exists
        if env
            .storage()
            .instance()
            .has(&DataKey::Deposit(session_id.clone()))
        {
            panic!("Session ID already exists");
        }

        // Get USDC token address
        let usdc_token: Address = env
            .storage()
            .instance()
            .get(&DataKey::UsdcToken)
            .expect("USDC token not set");

        // Transfer USDC from user to this contract
        let token_client = token::Client::new(&env, &usdc_token);
        token_client.transfer(&user, &env.current_contract_address(), &amount);

        // Get current ledger timestamp
        let timestamp = env.ledger().timestamp();

        // Create deposit record
        let deposit = Deposit {
            user: user.clone(),
            amount,
            session_id: session_id.clone(),
            claimed: false,
            timestamp,
        };

        // Store deposit
        env.storage()
            .instance()
            .set(&DataKey::Deposit(session_id.clone()), &deposit);

        // Add session_id to deposit list
        let mut deposit_list: Vec<String> = env
            .storage()
            .instance()
            .get(&DataKey::DepositList)
            .unwrap_or(Vec::new(&env));
        deposit_list.push_back(session_id.clone());
        env.storage()
            .instance()
            .set(&DataKey::DepositList, &deposit_list);

        // Emit PaymentReceived event
        env.events().publish(
            (Symbol::new(&env, "payment_received"),),
            PaymentReceived {
                user: user.clone(),
                amount,
                session_id: session_id.clone(),
                timestamp,
            },
        );
    }

    /// Admin claims USDC after card authorization succeeds
    pub fn claim(env: Env, session_id: String) {
        // Get admin
        let admin: Address = env
            .storage()
            .instance()
            .get(&DataKey::Admin)
            .expect("Admin not set");

        // Require admin authentication
        admin.require_auth();

        // Get deposit
        let mut deposit: Deposit = env
            .storage()
            .instance()
            .get(&DataKey::Deposit(session_id.clone()))
            .expect("Deposit not found");

        // Check if already claimed
        if deposit.claimed {
            panic!("Deposit already claimed");
        }

        // Get USDC token address
        let usdc_token: Address = env
            .storage()
            .instance()
            .get(&DataKey::UsdcToken)
            .expect("USDC token not set");

        // Transfer USDC from contract to admin
        let token_client = token::Client::new(&env, &usdc_token);
        token_client.transfer(&env.current_contract_address(), &admin, &deposit.amount);

        // Mark as claimed
        deposit.claimed = true;
        env.storage()
            .instance()
            .set(&DataKey::Deposit(session_id.clone()), &deposit);

        // Emit claim event
        env.events().publish(
            (Symbol::new(&env, "payment_claimed"),),
            (session_id, deposit.amount),
        );
    }

    /// Get deposit details
    pub fn get_deposit(env: Env, session_id: String) -> Option<Deposit> {
        env.storage()
            .instance()
            .get(&DataKey::Deposit(session_id))
    }

    /// Get all deposit session IDs
    pub fn get_all_deposits(env: Env) -> Vec<String> {
        env.storage()
            .instance()
            .get(&DataKey::DepositList)
            .unwrap_or(Vec::new(&env))
    }

    /// Get admin address
    pub fn get_admin(env: Env) -> Address {
        env.storage()
            .instance()
            .get(&DataKey::Admin)
            .expect("Admin not set")
    }

    /// Get USDC token address
    pub fn get_usdc_token(env: Env) -> Address {
        env.storage()
            .instance()
            .get(&DataKey::UsdcToken)
            .expect("USDC token not set")
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use soroban_sdk::{testutils::Address as _, Address, Env, String};

    #[test]
    fn test_deposit_and_claim() {
        let env = Env::default();
        env.mock_all_auths();

        let contract_id = env.register_contract(None, StellarPayEscrow);
        let client = StellarPayEscrowClient::new(&env, &contract_id);

        // Create test addresses
        let admin = Address::generate(&env);
        let user = Address::generate(&env);
        let usdc_token = Address::generate(&env);

        // Initialize contract
        client.initialize(&admin, &usdc_token);

        // Verify initialization
        assert_eq!(client.get_admin(), admin);
        assert_eq!(client.get_usdc_token(), usdc_token);

        // Test deposit (would need actual token contract in real test)
        let session_id = String::from_str(&env, "test_session_001");
        let amount: i128 = 10_000_000; // 100 USDC (7 decimals)

        // Note: In real test, we'd deploy a token contract and fund the user
        // For now, this demonstrates the contract structure

        println!("✅ Contract initialized successfully");
        println!("Admin: {:?}", admin);
        println!("USDC Token: {:?}", usdc_token);
    }
}
