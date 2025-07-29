// Test script for marketplace detection
// This can be run in the browser console to test the marketplace detection logic

function detectMarketplace(hostname) {
    // Amazon domain to marketplace mapping
    const domainToMarketplace = {
        'www.amazon.com': 'US',
        'www.amazon.ca': 'CA',
        'www.amazon.com.mx': 'MX',
        'www.amazon.de': 'DE',
        'www.amazon.co.uk': 'GB',
        'www.amazon.fr': 'FR',
        'www.amazon.it': 'IT',
        'www.amazon.es': 'ES',
        'www.amazon.nl': 'NL',
        'www.amazon.se': 'SE',
        'www.amazon.pl': 'PL',
        'www.amazon.com.be': 'BE'
    };
    
    // Check for exact match first
    if (domainToMarketplace[hostname]) {
        return domainToMarketplace[hostname];
    }
    
    // Check for subdomain patterns
    if (hostname.includes('amazon.com')) {
        return 'US';
    } else if (hostname.includes('amazon.ca')) {
        return 'CA';
    } else if (hostname.includes('amazon.com.mx')) {
        return 'MX';
    } else if (hostname.includes('amazon.de')) {
        return 'DE';
    } else if (hostname.includes('amazon.co.uk')) {
        return 'GB';
    } else if (hostname.includes('amazon.fr')) {
        return 'FR';
    } else if (hostname.includes('amazon.it')) {
        return 'IT';
    } else if (hostname.includes('amazon.es')) {
        return 'ES';
    } else if (hostname.includes('amazon.nl')) {
        return 'NL';
    } else if (hostname.includes('amazon.se')) {
        return 'SE';
    } else if (hostname.includes('amazon.pl')) {
        return 'PL';
    } else if (hostname.includes('amazon.com.be')) {
        return 'BE';
    }
    
    // Default to US if no match found
    return 'US';
}

// Test cases
const testCases = [
    'www.amazon.com',
    'www.amazon.ca',
    'www.amazon.com.mx',
    'www.amazon.de',
    'www.amazon.co.uk',
    'www.amazon.fr',
    'www.amazon.it',
    'www.amazon.es',
    'www.amazon.nl',
    'www.amazon.se',
    'www.amazon.pl',
    'www.amazon.com.be',
    'amazon.com',
    'www.amazon.de',
    'smile.amazon.com'
];

console.log('Testing marketplace detection:');
testCases.forEach(hostname => {
    const marketplace = detectMarketplace(hostname);
    console.log(`${hostname} -> ${marketplace}`);
});

// Expected results:
// www.amazon.com -> US
// www.amazon.ca -> CA
// www.amazon.com.mx -> MX
// www.amazon.de -> DE
// www.amazon.co.uk -> GB
// www.amazon.fr -> FR
// www.amazon.it -> IT
// www.amazon.es -> ES
// www.amazon.nl -> NL
// www.amazon.se -> SE
// www.amazon.pl -> PL
// www.amazon.com.be -> BE
// amazon.com -> US
// www.amazon.de -> DE
// smile.amazon.com -> US 