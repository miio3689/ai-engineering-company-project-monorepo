const cityOptions = {
  Colombia: ['Medellín', 'Bogotá', 'Cali'],
  'Estados Unidos': ['Miami', 'Orlando']
};

const locationOptions = {
  'Colombia|Medellín': [
    'Brasaland El Poblado',
    'Brasaland Laureles',
    'Brasaland Envigado',
    'Brasaland Sabaneta'
  ],
  'Colombia|Bogotá': ['Brasaland Usaquén', 'Brasaland Chapinero', 'Brasaland Zona Rosa'],
  'Colombia|Cali': ['Brasaland Granada', 'Brasaland Ciudad Jardín', 'Brasaland Unicentro'],
  'Estados Unidos|Miami': ['Brasaland Brickell', 'Brasaland Coral Gables'],
  'Estados Unidos|Orlando': ['Brasaland Downtown', 'Brasaland International Drive']
};

const form = document.getElementById('formulario-brasa-points');

if (form) {
  const successMessage = document.getElementById('success-message');
  const countrySelect = document.getElementById('country');
  const citySelect = document.getElementById('city');
  const locationSelect = document.getElementById('location');
  const birthDateField = document.getElementById('birthDate');

  const fields = {
    fullName: document.getElementById('fullName'),
    email: document.getElementById('email'),
    phone: document.getElementById('phone'),
    birthDate: birthDateField,
    country: countrySelect,
    city: citySelect,
    discovery: document.getElementById('discovery'),
    terms: document.getElementById('terms')
  };

  const errorMessages = {
    fullName: 'Ingresa tu nombre completo (nombre y apellido)',
    email: 'Ingresa un email válido (ejemplo: nombre@correo.com)',
    phone: 'El teléfono debe incluir código de país (ejemplo: +57 300 123 4567 o +1 305 123 4567)',
    country: 'Selecciona tu país',
    city: 'Selecciona tu ciudad',
    discovery: 'Cuéntanos cómo conociste Brasaland',
    birthDate: 'Debes ser mayor de 18 años para registrarte en Brasa Points',
    terms: 'Debes aceptar los términos del programa Brasa Points para continuar'
  };

  function fillSelect(select, placeholder, options) {
    select.innerHTML = '';
    const placeholderOption = document.createElement('option');
    placeholderOption.value = '';
    placeholderOption.textContent = placeholder;
    select.appendChild(placeholderOption);

    options.forEach((optionValue) => {
      const option = document.createElement('option');
      option.value = optionValue;
      option.textContent = optionValue;
      select.appendChild(option);
    });
  }

  function setFieldState(field, isValid, message) {
    const errorElement = document.getElementById(`${field.id}-error`);

    if (errorElement) {
      errorElement.classList.add('hidden');
      errorElement.textContent = '';
    }

    field.classList.remove('border-red-600', 'ring-4', 'ring-red-100', 'border-brasaAccent', 'ring-brasaAccent/20');
    field.setAttribute('aria-invalid', 'false');

    if (!isValid) {
      field.classList.add('border-red-600', 'ring-4', 'ring-red-100');
      field.setAttribute('aria-invalid', 'true');

      if (errorElement) {
        errorElement.textContent = message;
        errorElement.classList.remove('hidden');
      }

      return false;
    }

    if (field.type === 'checkbox' ? field.checked : field.value) {
      field.classList.add('border-brasaAccent', 'ring-4', 'ring-brasaAccent/20');
    }

    return true;
  }

  function isAdult(dateString) {
    if (!dateString) {
      return false;
    }

    const birthDate = new Date(`${dateString}T00:00:00`);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDifference = today.getMonth() - birthDate.getMonth();

    if (monthDifference < 0 || (monthDifference === 0 && today.getDate() < birthDate.getDate())) {
      age -= 1;
    }

    return age >= 18;
  }

  function validateFullName() {
    const value = fields.fullName.value.trim().replace(/\s+/g, ' ');
    return setFieldState(fields.fullName, value.split(' ').filter(Boolean).length >= 2, errorMessages.fullName);
  }

  function validateEmail() {
    const value = fields.email.value.trim();
    return setFieldState(fields.email, /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value), errorMessages.email);
  }

  function validatePhone() {
    const value = fields.phone.value.trim();
    const country = fields.country.value;
    const formatOk = /^\+(57|1)\s?[0-9 ]{7,}$/.test(value);
    const countryOk =
      (country === 'Colombia' && value.startsWith('+57')) ||
      (country === 'Estados Unidos' && value.startsWith('+1')) ||
      (!country && /^\+(57|1)/.test(value));

    return setFieldState(fields.phone, formatOk && countryOk, errorMessages.phone);
  }

  function validateCountry() {
    return setFieldState(fields.country, fields.country.value !== '', errorMessages.country);
  }

  function validateCity() {
    return setFieldState(fields.city, fields.city.value !== '', errorMessages.city);
  }

  function validateDiscovery() {
    return setFieldState(fields.discovery, fields.discovery.value !== '', errorMessages.discovery);
  }

  function validateBirthDate() {
    return setFieldState(fields.birthDate, isAdult(fields.birthDate.value), errorMessages.birthDate);
  }

  function validateTerms() {
    const errorElement = document.getElementById('terms-error');
    errorElement.classList.add('hidden');
    errorElement.textContent = '';
    fields.terms.setAttribute('aria-invalid', 'false');

    if (!fields.terms.checked) {
      fields.terms.setAttribute('aria-invalid', 'true');
      errorElement.textContent = errorMessages.terms;
      errorElement.classList.remove('hidden');
      return false;
    }

    return true;
  }

  function updateCities() {
    const country = countrySelect.value;
    const cities = cityOptions[country] || [];

    fillSelect(citySelect, 'Selecciona tu ciudad', cities);
    citySelect.disabled = cities.length === 0;
    fillSelect(locationSelect, 'Selecciona una ubicación', []);
    locationSelect.disabled = true;
  }

  function updateLocations() {
    const key = `${countrySelect.value}|${citySelect.value}`;
    const locations = locationOptions[key] || [];

    fillSelect(locationSelect, 'Selecciona una ubicación', locations);
    locationSelect.disabled = locations.length === 0;
  }

  function validateForm() {
    return [
      validateFullName(),
      validateEmail(),
      validatePhone(),
      validateCountry(),
      validateCity(),
      validateDiscovery(),
      validateBirthDate(),
      validateTerms()
    ].every(Boolean);
  }

  function resetVisualState() {
    Object.values(fields).forEach((field) => {
      field.classList.remove('border-red-600', 'ring-4', 'ring-red-100', 'border-brasaAccent', 'ring-brasaAccent/20');
      field.setAttribute('aria-invalid', 'false');
    });

    document.querySelectorAll('[id$="-error"]').forEach((element) => {
      element.textContent = '';
      element.classList.add('hidden');
    });
  }

  const adultLimit = new Date();
  adultLimit.setFullYear(adultLimit.getFullYear() - 18);
  birthDateField.max = adultLimit.toISOString().split('T')[0];

  countrySelect.addEventListener('change', () => {
    updateCities();
    validateCountry();
    validatePhone();
  });

  citySelect.addEventListener('change', () => {
    updateLocations();
    validateCity();
  });

  fields.fullName.addEventListener('blur', validateFullName);
  fields.email.addEventListener('blur', validateEmail);
  fields.phone.addEventListener('blur', validatePhone);
  fields.birthDate.addEventListener('change', validateBirthDate);
  fields.discovery.addEventListener('change', validateDiscovery);
  fields.terms.addEventListener('change', validateTerms);

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    successMessage.classList.add('hidden');

    if (!validateForm()) {
      const firstInvalidField = form.querySelector('[aria-invalid="true"]');

      if (firstInvalidField) {
        firstInvalidField.focus();
      }

      return;
    }

    successMessage.classList.remove('hidden');
    form.reset();
    updateCities();
    resetVisualState();
    successMessage.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  form.addEventListener('reset', () => {
    window.requestAnimationFrame(() => {
      successMessage.classList.add('hidden');
      updateCities();
      resetVisualState();
    });
  });

  updateCities();
}