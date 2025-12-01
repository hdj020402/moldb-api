#!/usr/bin/env python3
"""
Helper function to query molecule data from the moldb-api service.
This function automatically handles URL encoding of InChI identifiers.
"""

import requests
import urllib.parse
from typing import Optional, Dict, Any, List


def query_molecule(inchi: str, base_url: str = "http://localhost:8000") -> Optional[Dict[str, Any]]:
    """
    Query molecule data by InChI from the moldb-api service.
    
    This function automatically URL-encodes the InChI identifier before sending
    the request to the API, so users don't need to manually encode it.
    
    Args:
        inchi (str): The InChI identifier to query
        base_url (str, optional): The base URL of the moldb-api service. 
                                  Defaults to "http://localhost:8000".
    
    Returns:
        Optional[Dict[str, Any]]: The molecule data if found, None otherwise.
        
    Example:
        >>> data = query_molecule("InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1")
        >>> if data:
        ...     print(data["content"])
    """
    # URL encode the InChI identifier
    encoded_inchi = urllib.parse.quote(inchi, safe='')
    
    # Construct the full URL
    url = f"{base_url}/molecule/{encoded_inchi}"
    
    try:
        # Send the request
        response = requests.get(url)
        
        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            # Molecule not found
            return None
        else:
            # Other error
            response.raise_for_status()
    except requests.RequestException as e:
        # Handle request exceptions
        print(f"Error querying molecule: {e}")
        return None


def query_molecules_batch(inchis: List[str], base_url: str = "http://localhost:8000") -> Dict[str, str]:
    """
    Query multiple molecule data by InChI from the moldb-api service in a single request.
    
    This function automatically URL-encodes the InChI identifiers before sending
    the request to the API, so users don't need to manually encode them.
    
    Args:
        inchis (List[str]): List of InChI identifiers to query
        base_url (str, optional): The base URL of the moldb-api service. 
                                  Defaults to "http://localhost:8000".
    
    Returns:
        Dict[str, str]: Dictionary mapping InChI to content for found molecules.
        
    Example:
        >>> inchis = ["InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3", "InChI=1S/H2O/h1H2"]
        >>> results = query_molecules_batch(inchis)
        >>> for inchi, content in results.items():
        ...     print(f"{inchi}: {content[:50]}...")
    """
    # Construct the full URL
    url = f"{base_url}/molecules/batch"
    
    # Prepare the payload
    payload = {
        "inchis": [urllib.parse.quote(inchi, safe='') for inchi in inchis]
    }
    
    try:
        # Send the request
        response = requests.post(url, json=payload)
        
        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            # Other error
            response.raise_for_status()
    except requests.RequestException as e:
        # Handle request exceptions
        print(f"Error querying molecules batch: {e}")
        return {}


# Example usage
if __name__ == "__main__":
    # Example InChI with special characters
    inchi = "InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1"
    
    # Query the molecule data
    data = query_molecule(inchi)
    
    if data:
        print("Molecule found:")
        print(f"InChI: {data['inchi']}")
        print(f"Content: {data['content']}")
    else:
        print("Molecule not found")
    
    print("\n" + "="*50 + "\n")
    
    # Example batch query
    inchis = [
        "InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1",
        "InChI=1S/H2O/h1H2"
    ]
    
    # Query multiple molecules
    batch_results = query_molecules_batch(inchis)
    
    print("Batch query results:")
    for data in batch_results:
        print(f"InChI: {data['inchi']}")
        print(f"Content: {data['content'][:50]}...")
        print()
