INSERT INTO users (user_id, onboarding_cohort) VALUES
('USER-001', DATE '2026-01-01'),
('USER-002', DATE '2026-01-01'),
('USER-003', DATE '2026-02-01')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO merchants (
    merchant_id, merchant_name, merchant_segment, city, state, onboarding_cohort
) VALUES
('MERCHANT-001', 'Demo Retail North', 'SMB', 'Bengaluru', 'Karnataka', DATE '2026-01-01'),
('MERCHANT-002', 'Demo Online Services', 'ONLINE', 'Mumbai', 'Maharashtra', DATE '2026-01-01'),
('MERCHANT-003', 'Demo Enterprise South', 'ENTERPRISE', 'Hyderabad', 'Telangana', DATE '2026-02-01')
ON CONFLICT (merchant_id) DO NOTHING;
