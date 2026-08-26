import { BusinessEntityList } from "@/components/business-entity-list";
import { CampaignShortcut } from "@/components/campaign-workspace";

export default function ContactsPage() {
  return (
    <>
      <CampaignShortcut />
      <BusinessEntityList entity="contacts" />
    </>
  );
}
