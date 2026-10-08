import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainPage from './pages/MainPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import PaymentPage from './pages/PaymentPage';
import OrganizationPage from './pages/OrganizationPage';
import CreditPurchasePage from './pages/CreditPurchasePage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/main" element={<MainPage />} />
        <Route path="/payment" element={<PaymentPage />} />
        <Route path="/organization" element={<OrganizationPage />} />
        <Route path="/credits/payment" element={<CreditPurchasePage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
