-- ============================================================
-- Luma Booking Concierge — Seed Data
-- Run AFTER schema.sql
-- ============================================================


-- ============================================================
-- BRANCHES (2 rows)
-- ============================================================
insert into branches (id, name, location, address, phone, hours) values
(
    'b1a1a1a1-0001-0001-0001-000000000001',
    'Dubai Mall',
    'Downtown Dubai',
    'Unit 234, Level 2, The Dubai Mall, Downtown Dubai',
    '+97144001111',
    '{"mon":"10:00-22:00","tue":"10:00-22:00","wed":"10:00-22:00","thu":"10:00-22:00","fri":"10:00-23:00","sat":"10:00-23:00","sun":"10:00-22:00"}'
),
(
    'b2b2b2b2-0002-0002-0002-000000000002',
    'JBR',
    'Jumeirah Beach Residence',
    'Shop 12, The Walk, JBR, Dubai',
    '+97144002222',
    '{"mon":"10:00-21:00","tue":"10:00-21:00","wed":"10:00-21:00","thu":"10:00-21:00","fri":"10:00-22:00","sat":"10:00-22:00","sun":"10:00-21:00"}'
)
on conflict (id) do nothing;


-- ============================================================
-- ARTISTS (5 rows)
-- ============================================================
insert into artists (id, name, branch_id, speciality) values
('a1a1a1a1-0001-0001-0001-000000000001', 'Fatima Al Zahra', 'b1a1a1a1-0001-0001-0001-000000000001', 'Brow Specialist'),
('a2a2a2a2-0002-0002-0002-000000000002', 'Sara Ahmed',      'b1a1a1a1-0001-0001-0001-000000000001', 'SPMU Artist'),
('a3a3a3a3-0003-0003-0003-000000000003', 'Noor Hassan',     'b2b2b2b2-0002-0002-0002-000000000002', 'Medical Aesthetics'),
('a4a4a4a4-0004-0004-0004-000000000004', 'Lara Malik',      'b2b2b2b2-0002-0002-0002-000000000002', 'SPMU Artist'),
('a5a5a5a5-0005-0005-0005-000000000005', 'Dr. Amira Khalid','b1a1a1a1-0001-0001-0001-000000000001', 'Medical Aesthetics')
on conflict (id) do nothing;


-- ============================================================
-- SERVICES (14 rows — T1, T2, T3, and Consultation)
-- ============================================================
insert into services (id, name, category, service_tier, duration_minutes, price_aed, requires_consultation, requires_patch_test, requires_screening, is_medical, min_frequency_weeks, frequency_hard_block, description, is_consultation) values

-- T1 — Direct booking, no gate
('c1111111-0001-0001-0001-000000000001', 'Brow Threading',    'brow',    'T1',  30,   80.00, false, false, false, false, null, false, 'Classic brow shaping using threading technique',              false),
('c2222222-0002-0002-0002-000000000002', 'Brow Lamination',   'brow',    'T1',  60,  180.00, false, false, false, false,    6, false, 'Brow lamination for fuller brushed-up brows',                 false),
('c3333333-0003-0003-0003-000000000003', 'Brow Tint',         'brow',    'T1',  30,  100.00, false, false, false, false, null, false, 'Tinting to enhance brow colour and definition',               false),
('c4444444-0004-0004-0004-000000000004', 'Lash Tint',         'lash',    'T1',  30,  120.00, false, false, false, false, null, false, 'Lash tinting for darker more defined lashes',                 false),
('c5555555-0005-0005-0005-000000000005', 'Full Body Waxing',  'waxing',  'T1',  60,  250.00, false, false, false, false, null, false, 'Full body waxing service',                                    false),

-- T2 — Consultation + patch test required
('d1111111-0001-0001-0001-000000000001', 'Brow SPMU',         'spmu_brow',      'T2', 120, 1200.00, true,  true,  false, false, 42, false, 'Semi-permanent brow makeup',                         false),
('d2222222-0002-0002-0002-000000000002', 'Lip Blush',         'spmu_lip',       'T2', 120, 1500.00, true,  true,  false, false, 42, false, 'Semi-permanent lip colour and definition',            false),
('d3333333-0003-0003-0003-000000000003', 'Eyeliner SPMU',     'spmu_eyeliner',  'T2',  90, 1100.00, true,  true,  false, false, 42, false, 'Semi-permanent eyeliner tattoo',                     false),
('d4444444-0004-0004-0004-000000000004', 'Nano Brows',        'spmu_brow',      'T2', 150, 1400.00, true,  true,  false, false, 42, false, 'Ultra-fine hairstrokes using nano needle technique',  false),

-- T3 — Medical screening required
('e1111111-0001-0001-0001-000000000001', 'Anti-Wrinkle Injections', 'injectable',     'T3',  45, 1800.00, false, false, true,  true,  12, true,  'Botox treatment for fine lines and wrinkles',       false),
('e2222222-0002-0002-0002-000000000002', 'Lip Filler',              'injectable',     'T3',  45, 2000.00, false, false, true,  true,  12, true,  'Hyaluronic acid lip filler treatment',              false),
('e3333333-0003-0003-0003-000000000003', 'HydraFacial',             'medical_facial', 'T3',  60,  900.00, false, false, true,  true,   4, false, 'Medical-grade facial treatment',                   false),
('e4444444-0004-0004-0004-000000000004', 'Chemical Peel',           'medical_facial', 'T3',  45,  750.00, false, false, true,  true,   4, false, 'Clinical chemical peel treatment',                 false),

-- Consultation service (T1, free, is_consultation=true)
('f0000000-0001-0001-0001-000000000001', 'Consultation',      'consultation', 'T1',  60,    0.00, false, false, false, false, null, false, null,                                                  true)

on conflict (id) do nothing;


-- ============================================================
-- CLIENTS (primary demo client + 10 demo clients)
-- ============================================================
insert into clients (id, name, phone, email, created_at) values
('f1111111-0001-0001-0001-000000000001', 'Sarah Al Mansoori', '+971501234567', 'sarah@demo.com',     '2026-06-11 08:39:42.837062+00'),
('1c6690a5-584d-44c1-9406-7c225e9ca977', 'Demo Client 1',     '+97150000001',  'client1@demo.com',  '2026-06-12 06:13:00.76401+00'),
('bd735672-9137-463e-b5b2-0d93cefc990b', 'Demo Client 2',     '+97150000002',  'client2@demo.com',  '2026-06-12 06:13:00.76401+00'),
('29aacb89-2705-40cd-81fa-1f935670cef1', 'Demo Client 3',     '+97150000003',  'client3@demo.com',  '2026-06-12 06:13:00.76401+00'),
('d6ea6766-a58e-4a0b-994b-8a0df0d6ea5d', 'Demo Client 4',     '+97150000004',  'client4@demo.com',  '2026-06-12 06:13:00.76401+00'),
('8d5cdb65-4c3d-4e96-8388-efcd16f89ecf', 'Demo Client 5',     '+97150000005',  'client5@demo.com',  '2026-06-12 06:13:00.76401+00'),
('9efc1560-4edc-4d7e-a5bd-b4543c676421', 'Demo Client 6',     '+97150000006',  'client6@demo.com',  '2026-06-12 06:13:00.76401+00'),
('da9f93c1-5d76-4f79-a5e4-4ecfcf93c0c4', 'Demo Client 7',     '+97150000007',  'client7@demo.com',  '2026-06-12 06:13:00.76401+00'),
('85c62212-a8d6-4f2a-b45d-edd0ef3874fd', 'Demo Client 8',     '+97150000008',  'client8@demo.com',  '2026-06-12 06:13:00.76401+00'),
('928f0184-d338-43a7-98b3-e082d6d8f5b7', 'Demo Client 9',     '+97150000009',  'client9@demo.com',  '2026-06-12 06:13:00.76401+00'),
('d3971cd3-c9f4-4764-8e86-71017793ff71', 'Demo Client 10',    '+97150000010',  'client10@demo.com', '2026-06-12 06:13:00.76401+00')
on conflict (id) do nothing;


-- ============================================================
-- FAQS (20 rows)
-- ============================================================
insert into faqs (id, question, answer, category) values
('aa4cd6ba-7a2e-4c51-9975-6baee54eeb8b', 'What are your opening hours?',             'Dubai Mall is open Sunday to Thursday 10am-10pm, Friday and Saturday 10am-11pm. JBR is open Sunday to Thursday 10am-9pm, Friday and Saturday 10am-10pm.',                            'hours'),
('dac65925-0230-4aae-a545-5a4dc178ee08', 'Where are you located?',                   'We have two branches — Dubai Mall (Level 2, Unit 234) and JBR (Shop 12, The Walk).',                                                                                                  'location'),
('cf25e978-3aeb-4f36-85f3-95c681eff213', 'How much does brow threading cost?',        'Brow threading is AED 80 at both branches.',                                                                                                                                          'pricing'),
('60fa556d-0792-429a-89b2-df9c30a462b5', 'How much does brow lamination cost?',       'Brow lamination is AED 180 and takes about 60 minutes.',                                                                                                                              'pricing'),
('a5c83f31-41c1-478f-813e-93d687e1e1f1', 'What is brow SPMU?',                       'Brow SPMU is a cosmetic tattooing technique that creates natural-looking brows lasting 1-3 years. A free consultation and patch test are required before your first appointment.',     'services'),
('2d240837-5be9-4f12-959d-67911b2cce3a', 'Do I need a consultation for SPMU?',        'Yes — all SPMU treatments require a free 30-minute consultation and patch test at least 48 hours before your main appointment.',                                                      'policy'),
('fe050ea7-9eb6-4c7c-90e5-ed668015d049', 'How long does a patch test take?',          'The patch test is done during your free consultation and takes about 10 minutes. You need to wait 48 hours before your SPMU appointment.',                                            'policy'),
('efaab749-c243-42b8-b92d-83f76776e7e9', 'Can I cancel my appointment?',              'Yes, cancellations are accepted up to 24 hours before your appointment. Please contact our reception team to cancel or modify a booking.',                                            'policy'),
('496eaad7-37d1-42a5-aa59-fc692a52778c', 'What payment methods do you accept?',       'We accept all major credit and debit cards, Apple Pay, and cash. For bookings above AED 1,000 a 20% deposit is required.',                                                           'payment'),
('22258b2e-2e35-44ee-a0bd-10560d37cbeb', 'How long does lip filler last?',            'Lip filler typically lasts 6-12 months. We recommend waiting at least 12 weeks between treatments.',                                                                                  'services'),
('7669a8c9-e1be-4ee2-8042-71e779619dce', 'What is the minimum age for treatments?',   'Clients must be 18 or over for all SPMU and medical treatments.',                                                                                                                     'policy'),
('d240295c-d591-4f19-8eeb-b6f386d0ee02', 'Do you offer packages?',                    'Yes, we offer treatment packages with savings of up to 20%. Ask our team about current package offers when booking.',                                                                 'pricing'),
('427742d5-3cf4-423a-b06b-1ad0ef2a0644', 'How do I get to Dubai Mall branch?',        'Our Dubai Mall branch is on Level 2 near the Fashion Avenue entrance. Nearest metro is Burj Khalifa/Dubai Mall on the Red Line.',                                                    'location'),
('a9af88a0-8eba-4ea0-915a-9f3484e3956c', 'Is parking available?',                     'Yes, both locations have paid parking. Dubai Mall has parking across multiple levels. JBR has parking along The Walk.',                                                               'location'),
('dcd8864a-dc2c-42ad-9e50-78ffb6bf1be6', 'What should I do before brow lamination?',  'Avoid brow makeup on the day. Come with clean product-free brows. Avoid waxing or tinting 48 hours before your appointment.',                                                       'aftercare'),
('d1b1e0f6-2473-4448-b952-4b409307d86c', 'Where are your branches?',                  'We have branches at Dubai Mall and JBR.',                                                                                                                                             'location'),
('32e2bc52-75e7-40c8-b9c7-57890cbabc2a', 'Do I need a consultation for Brow SPMU?',   'Yes, a consultation and patch test are required.',                                                                                                                                    'spmu'),
('812c535d-8a1a-44e4-9e50-3b584211835d', 'How do I pay?',                             'A payment link is sent after booking.',                                                                                                                                               'payment'),
('b285005c-3a5a-4c45-a8a3-1c22914cb5e2', 'Can I cancel my booking?',                  'Yes, authenticated clients can cancel bookings.',                                                                                                                                     'booking'),
('cc7a8a2b-859f-4b8e-9916-447fbb225ddb', 'Do you offer HydraFacial?',                 'Yes, HydraFacial is available at both branches.',                                                                                                                                     'services')
on conflict (id) do nothing;


-- ============================================================
-- TIME_SLOTS
-- Fixed-ID slots used by seeded bookings + open slots for demos
-- The real system generates thousands of slots via a scheduler.
-- These are the 22 anchored slots referenced in actual bookings,
-- plus open slots for each service to enable live demo flows.
-- ============================================================
insert into time_slots (id, branch_id, service_id, artist_id, start_time, end_time, status) values

-- ── Slots referenced by seeded bookings (status = booked) ──────────────────
('a0000001-0001-0001-0001-000000000001', 'b1a1a1a1-0001-0001-0001-000000000001', 'c1111111-0001-0001-0001-000000000001', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-05 06:00:00+00', '2026-07-05 06:30:00+00', 'booked'),
('a0000002-0002-0002-0002-000000000002', 'b1a1a1a1-0001-0001-0001-000000000001', 'c1111111-0001-0001-0001-000000000001', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-05 08:00:00+00', '2026-07-05 08:30:00+00', 'booked'),
('a0000003-0003-0003-0003-000000000003', 'b1a1a1a1-0001-0001-0001-000000000001', 'c2222222-0002-0002-0002-000000000002', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-05 10:00:00+00', '2026-07-05 11:00:00+00', 'booked'),
('a0000004-0004-0004-0004-000000000004', 'b1a1a1a1-0001-0001-0001-000000000001', 'c2222222-0002-0002-0002-000000000002', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-06 08:00:00+00', '2026-07-06 09:00:00+00', 'booked'),
('a0000006-0006-0006-0006-000000000006', 'b1a1a1a1-0001-0001-0001-000000000001', 'd1111111-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-07 06:00:00+00', '2026-07-07 08:00:00+00', 'booked'),
('a0000007-0007-0007-0007-000000000007', 'b1a1a1a1-0001-0001-0001-000000000001', 'd1111111-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-08 06:00:00+00', '2026-07-08 08:00:00+00', 'booked'),
('a0000008-0008-0008-0008-000000000008', 'b2b2b2b2-0002-0002-0002-000000000002', 'e1111111-0001-0001-0001-000000000001', 'a3a3a3a3-0003-0003-0003-000000000003', '2026-07-09 07:00:00+00', '2026-07-09 07:45:00+00', 'booked'),
('a0000010-0010-0010-0010-000000000010', 'b1a1a1a1-0001-0001-0001-000000000001', 'd1111111-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-05 12:00:00+00', '2026-07-05 12:30:00+00', 'booked'),
('a0000011-0011-0011-0011-000000000011', 'b1a1a1a1-0001-0001-0001-000000000001', 'c3333333-0003-0003-0003-000000000003', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-05 07:00:00+00', '2026-07-05 07:30:00+00', 'booked'),
('a0000012-0012-0012-0012-000000000012', 'b1a1a1a1-0001-0001-0001-000000000001', 'c3333333-0003-0003-0003-000000000003', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-07 07:00:00+00', '2026-07-07 07:30:00+00', 'booked'),
('a0000016-0016-0016-0016-000000000016', 'b1a1a1a1-0001-0001-0001-000000000001', 'c1111111-0001-0001-0001-000000000001', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-06 06:00:00+00', '2026-07-06 06:30:00+00', 'booked'),
('a0000017-0017-0017-0017-000000000017', 'b1a1a1a1-0001-0001-0001-000000000001', 'c1111111-0001-0001-0001-000000000001', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-06 10:00:00+00', '2026-07-06 10:30:00+00', 'booked'),
('a0000020-0020-0020-0020-000000000020', 'b1a1a1a1-0001-0001-0001-000000000001', 'd1111111-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-12 06:00:00+00', '2026-07-12 08:00:00+00', 'booked'),
('a0000021-0021-0021-0021-000000000021', 'b1a1a1a1-0001-0001-0001-000000000001', 'd1111111-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-13 06:00:00+00', '2026-07-13 08:00:00+00', 'booked'),

-- ── Consultation slots (booked) ───────────────────────────────────────────
('a0000009-0009-0009-0009-000000000009', 'b2b2b2b2-0002-0002-0002-000000000002', 'e1111111-0001-0001-0001-000000000001', 'a3a3a3a3-0003-0003-0003-000000000003', '2026-07-10 07:00:00+00', '2026-07-10 07:45:00+00', 'booked'),
('f0000001-0001-0001-0001-000000000001', 'b1a1a1a1-0001-0001-0001-000000000001', 'f0000000-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-05 11:00:00+00', '2026-07-05 11:30:00+00', 'booked'),
('f0000003-0003-0003-0003-000000000003', 'b2b2b2b2-0002-0002-0002-000000000002', 'f0000000-0001-0001-0001-000000000001', 'a3a3a3a3-0003-0003-0003-000000000003', '2026-07-06 11:00:00+00', '2026-07-06 11:30:00+00', 'booked'),

-- ── Open slots — available for live demo flows ─────────────────────────────
-- T1: Brow Threading — Dubai Mall
('a0000013-0013-0013-0013-000000000013', 'b1a1a1a1-0001-0001-0001-000000000001', 'c1111111-0001-0001-0001-000000000001', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-14 08:00:00+00', '2026-07-14 08:30:00+00', 'available'),
('a0000014-0014-0014-0014-000000000014', 'b1a1a1a1-0001-0001-0001-000000000001', 'c1111111-0001-0001-0001-000000000001', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-14 10:00:00+00', '2026-07-14 10:30:00+00', 'available'),
('a0000015-0015-0015-0015-000000000015', 'b1a1a1a1-0001-0001-0001-000000000001', 'c1111111-0001-0001-0001-000000000001', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-14 12:00:00+00', '2026-07-14 12:30:00+00', 'available'),
('a0000030-0030-0030-0030-000000000030', 'b2b2b2b2-0002-0002-0002-000000000002', 'c1111111-0001-0001-0001-000000000001', 'a3a3a3a3-0003-0003-0003-000000000003', '2026-07-14 09:00:00+00', '2026-07-14 09:30:00+00', 'available'),

-- T1: Brow Lamination — Dubai Mall
('a0000005-0005-0005-0005-000000000005', 'b1a1a1a1-0001-0001-0001-000000000001', 'c2222222-0002-0002-0002-000000000002', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-14 14:00:00+00', '2026-07-14 15:00:00+00', 'available'),
('a0000031-0031-0031-0031-000000000031', 'b1a1a1a1-0001-0001-0001-000000000001', 'c2222222-0002-0002-0002-000000000002', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-15 10:00:00+00', '2026-07-15 11:00:00+00', 'available'),
('a0000032-0032-0032-0032-000000000032', 'b2b2b2b2-0002-0002-0002-000000000002', 'c2222222-0002-0002-0002-000000000002', 'a4a4a4a4-0004-0004-0004-000000000004', '2026-07-14 11:00:00+00', '2026-07-14 12:00:00+00', 'available'),

-- T1: Brow Tint — Dubai Mall
('a0000033-0033-0033-0033-000000000033', 'b1a1a1a1-0001-0001-0001-000000000001', 'c3333333-0003-0003-0003-000000000003', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-14 09:00:00+00', '2026-07-14 09:30:00+00', 'available'),
('a0000034-0034-0034-0034-000000000034', 'b1a1a1a1-0001-0001-0001-000000000001', 'c3333333-0003-0003-0003-000000000003', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-15 14:00:00+00', '2026-07-15 14:30:00+00', 'available'),

-- T1: Lash Tint — Dubai Mall
('a0000035-0035-0035-0035-000000000035', 'b1a1a1a1-0001-0001-0001-000000000001', 'c4444444-0004-0004-0004-000000000004', 'a1a1a1a1-0001-0001-0001-000000000001', '2026-07-14 13:00:00+00', '2026-07-14 13:30:00+00', 'available'),
('a0000036-0036-0036-0036-000000000036', 'b2b2b2b2-0002-0002-0002-000000000002', 'c4444444-0004-0004-0004-000000000004', 'a3a3a3a3-0003-0003-0003-000000000003', '2026-07-15 09:00:00+00', '2026-07-15 09:30:00+00', 'available'),

-- T2: Brow SPMU — both branches
('a0000040-0040-0040-0040-000000000040', 'b1a1a1a1-0001-0001-0001-000000000001', 'd1111111-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-14 10:00:00+00', '2026-07-14 12:00:00+00', 'available'),
('a0000041-0041-0041-0041-000000000041', 'b1a1a1a1-0001-0001-0001-000000000001', 'd1111111-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-15 10:00:00+00', '2026-07-15 12:00:00+00', 'available'),
('a0000042-0042-0042-0042-000000000042', 'b2b2b2b2-0002-0002-0002-000000000002', 'd1111111-0001-0001-0001-000000000001', 'a4a4a4a4-0004-0004-0004-000000000004', '2026-07-14 09:00:00+00', '2026-07-14 11:00:00+00', 'available'),
('a0000043-0043-0043-0043-000000000043', 'b2b2b2b2-0002-0002-0002-000000000002', 'd1111111-0001-0001-0001-000000000001', 'a4a4a4a4-0004-0004-0004-000000000004', '2026-07-16 09:00:00+00', '2026-07-16 11:00:00+00', 'available'),

-- T2: Lip Blush — Dubai Mall
('a0000044-0044-0044-0044-000000000044', 'b1a1a1a1-0001-0001-0001-000000000001', 'd2222222-0002-0002-0002-000000000002', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-15 13:00:00+00', '2026-07-15 15:00:00+00', 'available'),
('a0000045-0045-0045-0045-000000000045', 'b2b2b2b2-0002-0002-0002-000000000002', 'd2222222-0002-0002-0002-000000000002', 'a4a4a4a4-0004-0004-0004-000000000004', '2026-07-16 10:00:00+00', '2026-07-16 12:00:00+00', 'available'),

-- T2: Nano Brows — both branches
('a0000046-0046-0046-0046-000000000046', 'b1a1a1a1-0001-0001-0001-000000000001', 'd4444444-0004-0004-0004-000000000004', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-17 09:00:00+00', '2026-07-17 11:30:00+00', 'available'),
('a0000047-0047-0047-0047-000000000047', 'b2b2b2b2-0002-0002-0002-000000000002', 'd4444444-0004-0004-0004-000000000004', 'a4a4a4a4-0004-0004-0004-000000000004', '2026-07-17 10:00:00+00', '2026-07-17 12:30:00+00', 'available'),

-- T3: Anti-Wrinkle Injections — both branches
('a0000050-0050-0050-0050-000000000050', 'b1a1a1a1-0001-0001-0001-000000000001', 'e1111111-0001-0001-0001-000000000001', 'a5a5a5a5-0005-0005-0005-000000000005', '2026-07-14 11:00:00+00', '2026-07-14 11:45:00+00', 'available'),
('a0000051-0051-0051-0051-000000000051', 'b1a1a1a1-0001-0001-0001-000000000001', 'e1111111-0001-0001-0001-000000000001', 'a5a5a5a5-0005-0005-0005-000000000005', '2026-07-15 11:00:00+00', '2026-07-15 11:45:00+00', 'available'),
('a0000052-0052-0052-0052-000000000052', 'b2b2b2b2-0002-0002-0002-000000000002', 'e1111111-0001-0001-0001-000000000001', 'a3a3a3a3-0003-0003-0003-000000000003', '2026-07-14 08:00:00+00', '2026-07-14 08:45:00+00', 'available'),

-- T3: Lip Filler — both branches
('a0000053-0053-0053-0053-000000000053', 'b1a1a1a1-0001-0001-0001-000000000001', 'e2222222-0002-0002-0002-000000000002', 'a5a5a5a5-0005-0005-0005-000000000005', '2026-07-16 14:00:00+00', '2026-07-16 14:45:00+00', 'available'),
('a0000054-0054-0054-0054-000000000054', 'b2b2b2b2-0002-0002-0002-000000000002', 'e2222222-0002-0002-0002-000000000002', 'a3a3a3a3-0003-0003-0003-000000000003', '2026-07-16 10:00:00+00', '2026-07-16 10:45:00+00', 'available'),

-- T3: HydraFacial — both branches
('a0000055-0055-0055-0055-000000000055', 'b1a1a1a1-0001-0001-0001-000000000001', 'e3333333-0003-0003-0003-000000000003', 'a5a5a5a5-0005-0005-0005-000000000005', '2026-07-15 15:00:00+00', '2026-07-15 16:00:00+00', 'available'),
('a0000056-0056-0056-0056-000000000056', 'b2b2b2b2-0002-0002-0002-000000000002', 'e3333333-0003-0003-0003-000000000003', 'a3a3a3a3-0003-0003-0003-000000000003', '2026-07-15 09:00:00+00', '2026-07-15 10:00:00+00', 'available'),

-- T3: Chemical Peel — both branches
('a0000057-0057-0057-0057-000000000057', 'b1a1a1a1-0001-0001-0001-000000000001', 'e4444444-0004-0004-0004-000000000004', 'a5a5a5a5-0005-0005-0005-000000000005', '2026-07-17 13:00:00+00', '2026-07-17 13:45:00+00', 'available'),
('a0000058-0058-0058-0058-000000000058', 'b2b2b2b2-0002-0002-0002-000000000002', 'e4444444-0004-0004-0004-000000000004', 'a3a3a3a3-0003-0003-0003-000000000003', '2026-07-17 10:00:00+00', '2026-07-17 10:45:00+00', 'available'),

-- Consultation slots — both branches (open for T2 flows)
('a0000060-0060-0060-0060-000000000060', 'b1a1a1a1-0001-0001-0001-000000000001', 'f0000000-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-14 16:00:00+00', '2026-07-14 16:30:00+00', 'available'),
('a0000061-0061-0061-0061-000000000061', 'b1a1a1a1-0001-0001-0001-000000000001', 'f0000000-0001-0001-0001-000000000001', 'a2a2a2a2-0002-0002-0002-000000000002', '2026-07-15 16:00:00+00', '2026-07-15 16:30:00+00', 'available'),
('a0000062-0062-0062-0062-000000000062', 'b2b2b2b2-0002-0002-0002-000000000002', 'f0000000-0001-0001-0001-000000000001', 'a4a4a4a4-0004-0004-0004-000000000004', '2026-07-14 15:00:00+00', '2026-07-14 15:30:00+00', 'available'),
('a0000063-0063-0063-0063-000000000063', 'b2b2b2b2-0002-0002-0002-000000000002', 'f0000000-0001-0001-0001-000000000001', 'a4a4a4a4-0004-0004-0004-000000000004', '2026-07-16 15:00:00+00', '2026-07-16 15:30:00+00', 'available')

on conflict (id) do nothing;


-- ============================================================
-- SPMU_CLEARANCES
-- Sarah has an active clearance for spmu_brow (for T2 demo)
-- ============================================================
insert into spmu_clearances (id, client_id, visitor_contact, service_category, patch_test_done, patch_test_cleared, cleared_at, valid_until, created_at) values
(
    'b0000001-0001-0001-0001-000000000001',
    'f1111111-0001-0001-0001-000000000001',
    null,
    'spmu_brow',
    true,
    true,
    '2026-03-01 06:00:00+00',
    '2026-09-01 06:00:00+00',
    '2026-06-11 08:39:42.837062+00'
)
on conflict (id) do nothing;


-- ============================================================
-- MEDICAL_SCREENINGS
-- Sarah has an APPROVED injectable screening (T3 clearance demo)
-- One PENDING for frequency-block demo scenario
-- ============================================================
insert into medical_screenings (id, client_id, visitor_name, visitor_contact, service_category, answers, flagged_questions, status, reviewed_by, reviewed_at, approved_until, created_at) values
(
    'SCR-2026-0001',
    'f1111111-0001-0001-0001-000000000001',
    'Sarah Al Mansoori',
    '+971501234567',
    'injectable',
    '{"q1_pregnant":false,"q2_blood_thinners":false,"q3_allergies":false,"q4_prior_procedures":false,"q5_active_infection":false,"q6_autoimmune":false}',
    '[]',
    'APPROVED',
    'Dr. Layla Hassan',
    '2026-04-01 06:00:00+00',
    '2026-07-30 06:00:00+00',
    '2026-06-11 08:39:42.837062+00'
),
(
    'SCR-2026-DEMO1',
    null,
    'Demo Client',
    '+971500000001',
    'injectable',
    '{}',
    '[]',
    'APPROVED',
    'Medical Team',
    '2026-06-12 06:13:34.87908+00',
    '2026-09-10 06:13:34.87908+00',
    '2026-06-12 06:13:34.87908+00'
),
-- PENDING screening — used to demo the "screening under review" path (Flow 10)
(
    'SCR-2026-PENDING',
    null,
    'Demo Pending',
    '+971500000099',
    'injectable',
    '{"q1_pregnant":false,"q2_blood_thinners":false,"q3_allergies":false,"q4_prior_procedures":false,"q5_active_infection":false,"q6_autoimmune":false}',
    '[]',
    'PENDING',
    null,
    null,
    null,
    '2026-06-12 08:00:00+00'
)
on conflict (id) do nothing;


-- ============================================================
-- BOOKINGS
-- Key seeded bookings from real usage:
--   BKG-2026-00001 — Sarah's completed injectable booking
--                    (used for frequency hard-block demo — booked ~6 weeks ago,
--                     12-week block means she cannot rebook until ~Aug 2026)
-- Remaining bookings from testing sessions are included for log completeness.
-- ============================================================
insert into bookings (id, client_id, visitor_name, visitor_contact, service_id, branch_id, slot_id, artist_id, status, notes, booking_type, payment_type, deposit_amount_aed, balance_due_aed, payment_status, payment_link, screening_ref, clearance_ref, consent_status, channel, booking_source, created_at, updated_at) values

-- Sarah — completed injectable booking (enables frequency hard-block demo for T3)
('BKG-2026-00001', 'f1111111-0001-0001-0001-000000000001', null, null,
 'e1111111-0001-0001-0001-000000000001', 'b2b2b2b2-0002-0002-0002-000000000002',
 'a0000008-0008-0008-0008-000000000008', 'a3a3a3a3-0003-0003-0003-000000000003',
 'completed', null, 'single', 'full_upfront', 0.00, 0.00, 'paid',
 null, null, null, 'not_required', 'web', 'ai_concierge',
 '2026-05-01 07:00:00+00', '2026-06-11 08:39:42.837062+00'),

-- Sarah — confirmed Brow SPMU booking (T2, deposit required)
('BKG-2026-M2O2', 'f1111111-0001-0001-0001-000000000001', null, null,
 'd1111111-0001-0001-0001-000000000001', 'b1a1a1a1-0001-0001-0001-000000000001',
 'a0000007-0007-0007-0007-000000000007', 'a2a2a2a2-0002-0002-0002-000000000002',
 'confirmed', null, 'single', 'deposit_20pct', 240.00, 960.00, 'payment_initiated',
 'https://pay.stripe.com/test/BKG-2026-M2O2?amount=24000', null, null, 'not_required',
 'web', 'ai_concierge', '2026-06-11 09:54:22.688733+00', '2026-06-11 09:54:23.977958+00'),

-- Visitor — Brow Threading (T1, payment link demo)
('BKG-2026-50JB', null, null, null,
 'c1111111-0001-0001-0001-000000000001', 'b1a1a1a1-0001-0001-0001-000000000001',
 'a0000001-0001-0001-0001-000000000001', null,
 'confirmed', null, 'single', 'full_upfront', 80.00, 0.00, 'payment_initiated',
 'https://pay.stripe.com/test/BKG-2026-50JB?amount=8000', null, null, 'not_required',
 'web', 'ai_concierge', '2026-06-11 09:43:26.467268+00', '2026-06-11 09:43:27.771719+00'),

-- Visitor — Brow SPMU Consultation (T2 flow)
('CON-2026-M0VK', null, null, null,
 'd1111111-0001-0001-0001-000000000001', 'b1a1a1a1-0001-0001-0001-000000000001',
 'a0000010-0010-0010-0010-000000000010', null,
 'confirmed', null, 'consultation', 'free', 0.00, 0.00, 'not_required',
 null, null, null, 'not_required', 'web', 'ai_concierge',
 '2026-06-11 09:44:01.794786+00', '2026-06-11 09:44:03.064617+00')

on conflict (id) do nothing;


-- ============================================================
-- VISITORS (real captured visitors from testing)
-- ============================================================
insert into visitors (id, name, contact, created_at) values
('cfcf39f1-23f5-4f00-a901-6d8cae92c395', 'Afreen',  '0504336917',           '2026-06-11 13:36:30.74906+00'),
('417215ca-aff6-417a-9344-3eac8151cfd5', 'Sara',    '0585834775',           '2026-06-11 13:58:31.140088+00'),
('f439f6b7-ba79-44a5-8a68-153f6baea7ad', 'Lama',    '056839375',            '2026-06-11 14:19:35.889148+00'),
('67680a32-b8b6-4dc7-8d06-2d083283f210', 'Afreen',  'afreenzakkir8@gmail.com', '2026-06-11 10:52:20.899019+00')
on conflict (contact) do nothing;


-- ============================================================
-- NOTE ON TIME_SLOTS AT SCALE
-- ============================================================
-- The real database has ~7,130 time slots generated by a scheduler.
-- The seed above includes ~55 anchored slots (those referenced by
-- seeded bookings) plus open slots for each service/branch combo
-- to enable all demo flows without code changes.
--
-- To generate a full slot grid for future dates, run:
--
--   SELECT generate_slots('2026-07-01', '2026-09-30');
--
-- or use your slot-generation script (see scripts/generate_slots.py).
-- ============================================================
