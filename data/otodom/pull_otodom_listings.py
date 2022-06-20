import sys
import yaml
import json
sys.path.append('..')
from pull_listings import PullPropertyListings


class PullOtodomListings(PullPropertyListings):
    """
    Pull property listings from the Polish property listings site, Otodom.
    """
    def __init__(self):
        root_url = 'https://www.otodom.pl'
        page_param = 'page'
        listing_categories = {'apartments': 'pl/oferty/wynajem/mieszkanie/cala-polska', 'houses': 'pl/oferty/wynajem/dom/cala-polska'}
        listing_details_translations = yaml.safe_load(open('listing_details_translations.yml'))
        super().__init__(root_url=root_url,
                         page_param=page_param,
                         listing_categories=listing_categories,
                         listing_details_translations=listing_details_translations)


    def get_listings_list(self, listings_page_soup):
        """
        Get the list of listings from the listings page.

        Parameters
        ----------
        listings_page_soup : BeautifulSoup (required)
            Soup of the listings page.

        Returns
        -------
        listings_list : list
            List of listings.
        """
        listings_list = listings_page_soup.find("body")\
                                          .find("div", {"role": "main", "class": ["css-1sxg93g", "e76enq86"]})\
                                          .find("div", {"data-cy": "search.listing"}, recursive=False)\
                                          .find("ul", {"class": ["css-14cy79a", "e3x1uf07"]})\
                                          .find_all("li")
        return listings_list


    def get_listing_url(self, listing_soup):
        """
        Get the relative url of a single listing from the single listing soup on the listings page.

        Parameters
        ----------
        listing_soup : BeautifulSoup (required)
            Soup of the listing from the listings list.

        Returns
        -------
        url : string
            Relative URL of the single listing.
        """
        listing_link = listing_soup.find('a', {'data-cy': 'listing-item-link'})
        if listing_link:
            return listing_link['href']


    def get_listing_details(self, listing_page_soup):
        """
        Get details of the property listing from the listing soup.

        Parameters
        ----------
        listing_page_soup : BeautifulSoup (required)
            Soup of the listing page.

        Returns
        -------
        listing_details : dict
            Dictionary mapping listing detail names to content, e.g. {"title": "My listing", "category": "flat"}.
        """
        listing_details = {}
        header_section = listing_page_soup.find("body").find("main").find("header")
        listing_details["title"] = header_section.find("h1").text.strip()
        listing_details["price"] = header_section.find("strong", {"data-cy": "adPageHeaderPrice"}, recursive=False).text.strip()

        # Extract information from the details section
        details_section = listing_page_soup.find("div", {"data-testid": "ad.top-information.table"})\
                                           .find("div", recursive=False)\
                                           .find_all("div", recursive=False)
        for item in details_section:
            detail_title = item.find_all("div", recursive=False)[0].find("div").text.strip()
            try:
                detail_value = item.find_all("div", recursive=False)[1].find("div").text.strip()
            except AttributeError:
                detail_value = None

            if detail_title not in self.listing_details_translations:
                print(f'Unrecognised listing detail: {detail_title}')
                continue

            detail_title_trans = self.listing_details_translations[detail_title]
            listing_details[detail_title_trans] = detail_value

        # Get the latitude and longitude
        script_details = listing_page_soup.find("script", {"id": "__NEXT_DATA__"})
        coordinates = json.loads(script_details.text)["props"]["pageProps"]["ad"]["location"]["coordinates"]
        listing_details["latitude"] = coordinates["latitude"]
        listing_details["longitude"] = coordinates["longitude"]

        return listing_details


    def process_listing_data(self, data):
        """
        Process the dataset of listings.

        Parameters
        ----------
        data : Pandas DataFrame (required)
            Pandas DataFrame with one row per listing.
        """
        # Process the data to convert numbers with units to just numbers
        def convert_units_to_num(price, unit=None):
            try:
                price_num = float(str(price).strip().split(unit)[0].replace(',','.').replace(' ',''))
                return price_num
            except:
                return
        data['price_num'] = data['price'].apply(lambda x: convert_units_to_num(x, unit='zł'))
        data['surface_area_m2_num'] = data['surface_area_m2'].apply(lambda x: convert_units_to_num(x, unit='m²'))
        data['latitude'] = data['latitude'].apply(lambda x: convert_units_to_num(x))
        data['longitude'] = data['longitude'].apply(lambda x: convert_units_to_num(x))
        data['price_utilities_pln_num'] = data['price_utilities_pln'].apply(lambda x: convert_units_to_num(x, unit='zł/miesiąc'))

        # Calculate price per m2
        def divide_ignore_nan(first, second):
            if first!=first or second!=second: return
            if first is None or second is None: return
            if second==0: return
            return first/second
        data['price_zl_per_m2_num'] = data.apply(lambda row: divide_ignore_nan(row['price_num'], row['surface_area_m2_num']), axis=1)

        # Order the columns so that the appending to the data is consistent
        columns_order = ['title', 'price', 'price_num', 'price_zl_per_m2_num', 'surface_area_m2_num', 'price_utilities_pln_num', 'latitude', 'longitude']
        columns_order += [item for item in self.listing_details_translations.values() if item not in columns_order] + ['url']
        if 'listing_page_category' in data.columns:
            columns_order += ['listing_page_category']
        for column in columns_order:
            if column not in data.columns:
                data[column] = ''
        missed_columns = [column for column in data.columns if column not in columns_order]
        if missed_columns:
            raise RuntimeError(f'Missing columns: {missed_columns}')
        data = data[columns_order]

        return data


if __name__ == "__main__":
    listings_puller = PullOtodomListings()
    listings_puller.pull_listing_categories(data_write_path='raw/2022-06-13_otodom_listings.csv',
                                            categories=['houses', 'apartments'],
                                            page_start=1)
